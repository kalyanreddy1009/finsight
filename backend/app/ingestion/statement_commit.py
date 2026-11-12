"""Idempotent commit of a reviewed statement to the double-entry ledger."""

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.database import seed
from app.database.session import transaction
from app.finance.ledger_service import LedgerService
from app.ingestion.pipeline import (
    StatementNotFoundError,
    find_duplicate_transaction,
    find_provisional_match,
)

_APPROVED_ROW_STATUSES = ("AUTO_APPROVED", "USER_APPROVED")


class StatementNotReconciledError(Exception):
    """The statement cannot be committed yet (unreconciled, import errors or pending rows)."""


@dataclass(frozen=True)
class CommitResult:
    statement_id: str
    committed_count: int
    skipped_count: int
    already_committed: bool
    snapshot_written: bool = False


def commit_statement(conn: sqlite3.Connection, statement_id: str, *, idempotency_key: str) -> CommitResult:
    if not isinstance(idempotency_key, str) or not idempotency_key:
        raise ValueError("idempotency_key must be a non-empty string.")
    with transaction(conn):
        stmt = conn.execute("SELECT * FROM statements WHERE id = ?", (statement_id,)).fetchone()
        if stmt is None:
            raise StatementNotFoundError("Unknown statement.")
        if stmt["processing_status"] == "APPROVED":
            return CommitResult(statement_id, 0, 0, True)
        if stmt["processing_status"] != "REVIEW_REQUIRED":
            raise ValueError("Statement is not awaiting review.")
        _require_committable(conn, stmt)
        ledger = LedgerService(conn)
        _post_opening_balance(conn, ledger, stmt)
        rows = conn.execute(
            "SELECT * FROM statement_rows WHERE statement_id = ? ORDER BY row_index", (statement_id,)
        ).fetchall()
        committed = 0
        claimed: set[str] = set()
        for row in rows:
            if row["row_status"] not in _APPROVED_ROW_STATUSES:
                continue
            provisional_id = _recheck_row(conn, stmt, row, claimed)
            if provisional_id is _DUPLICATE:
                continue
            _commit_row(conn, ledger, stmt, row, provisional_id)
            committed += 1
        snapshot = _finalize(conn, stmt, committed, idempotency_key)
        return CommitResult(statement_id, committed, len(rows) - committed, False, snapshot)


_DUPLICATE: Any = object()


def _recheck_row(
    conn: sqlite3.Connection, stmt: sqlite3.Row, row: sqlite3.Row, claimed: set[str]
) -> str | None:
    """Re-run duplicate and provisional matching against the ledger as it is right now.

    Returns ``_DUPLICATE`` (after marking the row) if the row now repeats a committed
    transaction, otherwise the provisional transaction id to upgrade, or None.
    """
    if not row["duplicate_override"]:
        duplicate_of = find_duplicate_transaction(
            conn,
            stmt["account_id"],
            direction=row["direction"],
            amount_minor=row["amount_minor"],
            external_reference=row["external_reference"],
            dedup_fingerprint=row["dedup_fingerprint"],
            exclude_statement_id=stmt["id"],
        )
        if duplicate_of is not None:
            conn.execute(
                "UPDATE statement_rows SET row_status = 'DUPLICATE', duplicate_of_transaction_id = ? "
                "WHERE id = ?",
                (duplicate_of, row["id"]),
            )
            return _DUPLICATE
    provisional_id = find_provisional_match(
        conn,
        stmt["account_id"],
        direction=row["direction"],
        amount_minor=row["amount_minor"],
        tx_date=date.fromisoformat(row["tx_date"]),
        external_reference=row["external_reference"],
        claimed=claimed,
    )
    if provisional_id is not None:
        claimed.add(provisional_id)
    conn.execute(
        "UPDATE statement_rows SET provisional_match_transaction_id = ? WHERE id = ?",
        (provisional_id, row["id"]),
    )
    return provisional_id


def _require_committable(conn: sqlite3.Connection, stmt: sqlite3.Row) -> None:
    if stmt["reconciliation_diff_minor"] != 0:
        raise StatementNotReconciledError("Statement does not reconcile to its closing balance.")
    sid = stmt["id"]
    if conn.execute("SELECT 1 FROM import_errors WHERE statement_id = ? LIMIT 1", (sid,)).fetchone():
        raise StatementNotReconciledError("Statement has unresolved import errors.")
    if conn.execute(
        "SELECT 1 FROM statement_rows WHERE statement_id = ? AND row_status = 'PENDING_REVIEW' LIMIT 1",
        (sid,),
    ).fetchone():
        raise StatementNotReconciledError("Statement still has rows pending review.")


def _post_opening_balance(conn: sqlite3.Connection, ledger: LedgerService, stmt: sqlite3.Row) -> None:
    opening = stmt["opening_balance_minor"]
    if opening == 0:
        return
    has_entries = conn.execute(
        "SELECT 1 FROM journal_lines l JOIN journal_entries e ON e.id = l.journal_entry_id "
        "WHERE l.account_id = ? AND e.is_provisional = 0 LIMIT 1",
        (stmt["account_id"],),
    ).fetchone()
    if has_entries:
        return
    ledger.record_opening_balance(
        account_id=stmt["account_id"],
        amount_minor=opening,
        entry_date=date.fromisoformat(stmt["statement_start_date"]),
        idempotency_key=f"stmt:{stmt['id']}:opening",
        statement_id=stmt["id"],
    )


def _commit_row(
    conn: sqlite3.Connection,
    ledger: LedgerService,
    stmt: sqlite3.Row,
    row: sqlite3.Row,
    provisional_id: str | None,
) -> None:
    tx_id = None
    if provisional_id:
        tx_id = _upgrade_provisional(conn, stmt, row, provisional_id)
    if tx_id is None:
        tx_id = _post_new(ledger, stmt, row)
        conn.execute(
            "UPDATE transactions SET review_status = ?, extracted_vpa = ?, confidence_score = ?, "
            "is_verified = ? WHERE id = ?",
            (
                row["row_status"], row["extracted_vpa"], row["confidence_score"],
                row["balance_verified"], tx_id,
            ),
        )  # fmt: skip
    conn.execute(
        "UPDATE statement_rows SET row_status = 'COMMITTED', committed_transaction_id = ? WHERE id = ?",
        (tx_id, row["id"]),
    )


def _post_new(ledger: LedgerService, stmt: sqlite3.Row, row: sqlite3.Row) -> str:
    is_debit = row["direction"] == "DEBIT"
    category_id = row["suggested_category_id"] or (
        seed.UNCATEGORIZED_EXPENSE_CATEGORY_ID if is_debit else seed.UNCATEGORIZED_INCOME_CATEGORY_ID
    )
    common: dict[str, Any] = {
        "category_id": category_id,
        "amount_minor": row["amount_minor"],
        "tx_date": date.fromisoformat(row["tx_date"]),
        "idempotency_key": f"stmt:{stmt['id']}:{row['row_index']}",
        "statement_id": stmt["id"],
        "external_reference": row["external_reference"],
        "dedup_fingerprint": row["dedup_fingerprint"],
        "description": row["raw_description"],
        "clean_description": row["clean_description"],
        "merchant_id": row["merchant_id"],
    }
    if is_debit:
        return ledger.record_expense(source_account_id=stmt["account_id"], **common)
    return ledger.record_income(dest_account_id=stmt["account_id"], **common)


def _upgrade_provisional(
    conn: sqlite3.Connection, stmt: sqlite3.Row, row: sqlite3.Row, provisional_id: str
) -> str | None:
    """Promote the matched provisional transaction in place; None if it is no longer provisional."""
    tx = conn.execute(
        "SELECT id, journal_entry_id FROM transactions WHERE id = ? AND review_status = 'PROVISIONAL'",
        (provisional_id,),
    ).fetchone()
    if tx is None:
        return None
    updated = conn.execute(
        "UPDATE journal_entries SET is_provisional = 0, source_statement_id = ? "
        "WHERE id = ? AND is_provisional = 1",
        (stmt["id"], tx["journal_entry_id"]),
    )
    if updated.rowcount != 1:
        raise ValueError("Provisional journal entry could not be upgraded.")
    conn.execute(
        "UPDATE transactions SET statement_id = ?, review_status = ?, external_reference = ?, "
        "dedup_fingerprint = ?, description = ?, clean_description = ?, "
        "merchant_id = COALESCE(?, merchant_id), extracted_vpa = COALESCE(?, extracted_vpa), "
        "confidence_score = ?, is_verified = ?, version = version + 1, "
        "updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
        (
            stmt["id"], row["row_status"], row["external_reference"], row["dedup_fingerprint"],
            row["raw_description"], row["clean_description"], row["merchant_id"], row["extracted_vpa"],
            row["confidence_score"], row["balance_verified"], tx["id"],
        ),
    )  # fmt: skip
    return tx["id"]


def _ledger_balance_as_of(conn: sqlite3.Connection, account_id: str, as_of: str) -> int:
    """Sum of posted journal lines for the account dated on or before ``as_of`` (ISO date)."""
    row = conn.execute(
        "SELECT COALESCE(SUM(l.signed_amount_minor), 0) AS bal FROM journal_lines l "
        "JOIN journal_entries e ON e.id = l.journal_entry_id "
        "WHERE e.status = 'POSTED' AND l.account_id = ? AND e.entry_date <= ?",
        (account_id, as_of),
    ).fetchone()
    return int(row["bal"])


def _finalize(
    conn: sqlite3.Connection,
    stmt: sqlite3.Row,
    committed: int,
    idempotency_key: str,
) -> bool:
    """Mark the statement approved; return whether a reconciled balance snapshot was written."""
    conn.execute(
        "UPDATE statements SET processing_status = 'APPROVED', "
        "approved_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
        (stmt["id"],),
    )
    as_of_end = _ledger_balance_as_of(conn, stmt["account_id"], stmt["statement_end_date"])
    snapshot = as_of_end == stmt["closing_balance_minor"]
    if snapshot:
        conn.execute(
            "INSERT INTO account_balance_snapshots (id, account_id, snapshot_date, balance_minor, source) "
            "VALUES (?, ?, ?, ?, 'STATEMENT_RECONCILED') ON CONFLICT (account_id, snapshot_date) "
            "DO UPDATE SET balance_minor = excluded.balance_minor, source = excluded.source",
            (
                str(uuid.uuid4()),
                stmt["account_id"],
                stmt["statement_end_date"],
                stmt["closing_balance_minor"],
            ),
        )
    conn.execute(
        "INSERT INTO audit_events (id, event_type, target_object_type, target_object_id, metadata_json) "
        "VALUES (?, 'STATEMENT_COMMITTED', 'statement', ?, ?)",
        (
            str(uuid.uuid4()), stmt["id"],
            json.dumps({"committed": committed, "idempotency_key": idempotency_key}, sort_keys=True),
        ),
    )  # fmt: skip
    return snapshot
