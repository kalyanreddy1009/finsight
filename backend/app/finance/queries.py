"""Read-side SQL for the API (lists, filters, dashboard) plus the few multi-step writes it needs.

All SQL is parameterised; dynamic parts are fixed fragments chosen in code, never user input.
"""

import base64
import binascii
import calendar
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from app.database.session import transaction
from app.finance import chart
from app.finance.ledger_service import LedgerService
from app.finance.safe_to_spend import calculate_safe_to_spend_minor

Record = dict[str, Any]

HIDDEN_ACCOUNT_SUBTYPES = ("REIMBURSEMENT_CLEARING", "OPENING_EQUITY", "SYSTEM_CATEGORY")
LIQUID_SUBTYPES = ("BANK_SAVINGS", "BANK_CURRENT", "CASH", "WALLET")
UPCOMING_BILL_DAYS = 7
OBLIGATION_DAYS = 30
_ESCAPE = "\\"

# Deliberately excludes encrypted_pdf_password.
_ACCOUNT_COLUMNS = (
    "id, name, account_class, account_subtype, institution, currency, opening_balance_minor, "
    "current_balance_minor, credit_limit_minor, billing_day, due_day, is_liquid, is_active, version, "
    "created_at, updated_at"
)
_ACCOUNT_BOOLS = ("is_liquid", "is_active")
_CATEGORY_COLUMNS = (
    "id, name, parent_category_id, category_type, default_tax_section, is_discretionary, "
    "is_sensitive_private, is_system_category, created_at"
)
_CATEGORY_BOOLS = ("is_discretionary", "is_sensitive_private", "is_system_category")
_TX_FROM = (
    "FROM transactions t JOIN journal_entries e ON e.id = t.journal_entry_id "
    "JOIN accounts a ON a.id = t.account_id JOIN accounts cp ON cp.id = t.counterparty_account_id "
    "LEFT JOIN categories c ON c.id = t.category_id"
)
_TX_SELECT = (
    "SELECT t.id, t.journal_entry_id, e.entry_type, t.account_id, a.name AS account_name, "
    "t.counterparty_account_id, cp.name AS counterparty_account_name, t.category_id, "
    "c.name AS category_name, t.transaction_date, t.description, t.clean_description, t.amount_minor, "
    "t.user_share_minor, t.direction, t.transaction_type, t.linked_transaction_id, t.tax_section, "
    "t.is_verified, t.review_status, t.notes, t.version, t.created_at, t.updated_at " + _TX_FROM
)
_SPLIT_SELECT = (
    "SELECT s.id, s.transaction_id, s.counterparty_name, s.counterparty_vpa, s.owed_amount_minor, "
    "s.settled_amount_minor, s.owed_amount_minor - s.settled_amount_minor AS outstanding_minor, "
    "s.status, s.settlement_transaction_id, s.created_at, t.transaction_date, "
    "t.clean_description AS description FROM reimbursable_splits s "
    "JOIN transactions t ON t.id = s.transaction_id"
)


def _record(row: sqlite3.Row, bools: tuple[str, ...] = ()) -> Record:
    data = dict(row)
    for name in bools:
        data[name] = bool(data[name])
    return data


class VersionConflictError(Exception):
    def __init__(self, current: Record) -> None:
        super().__init__("Version conflict.")
        self.current = current


# ---------------------------------------------------------------- accounts


def list_accounts(conn: sqlite3.Connection) -> list[Record]:
    marks = ",".join("?" * len(HIDDEN_ACCOUNT_SUBTYPES))
    rows = conn.execute(
        f"SELECT {_ACCOUNT_COLUMNS} FROM accounts WHERE account_subtype NOT IN ({marks}) "  # noqa: S608
        "ORDER BY account_class, name, id",
        HIDDEN_ACCOUNT_SUBTYPES,
    ).fetchall()
    return [_record(r, _ACCOUNT_BOOLS) for r in rows]


def get_account(conn: sqlite3.Connection, account_id: str) -> Record | None:
    row = conn.execute(f"SELECT {_ACCOUNT_COLUMNS} FROM accounts WHERE id = ?", (account_id,)).fetchone()  # noqa: S608
    return _record(row, _ACCOUNT_BOOLS) if row else None


@dataclass(frozen=True)
class OpeningBalance:
    amount_minor: int  # positive; for liabilities it is the amount owed
    on: date


def create_account_with_opening(
    conn: sqlite3.Connection, opening: OpeningBalance | None, **fields: Any
) -> Record:
    """Create an account and, if given, its opening balance in one transaction."""
    with transaction(conn):
        account_id = chart.create_account(conn, **fields)
        if opening is not None:
            signed = -opening.amount_minor if fields["account_class"] == "LIABILITY" else opening.amount_minor
            LedgerService(conn).record_opening_balance(
                account_id=account_id,
                amount_minor=signed,
                entry_date=opening.on,
                idempotency_key=f"opening-balance:{account_id}",
            )
            conn.execute("UPDATE accounts SET opening_balance_minor = ? WHERE id = ?", (signed, account_id))
    account = get_account(conn, account_id)
    assert account is not None
    return account


# -------------------------------------------------------------- categories


def list_categories(conn: sqlite3.Connection) -> list[Record]:
    rows = conn.execute(
        f"SELECT {_CATEGORY_COLUMNS} FROM categories ORDER BY category_type, name, id"  # noqa: S608
    ).fetchall()
    return [_record(r, _CATEGORY_BOOLS) for r in rows]


def get_category(conn: sqlite3.Connection, category_id: str) -> Record | None:
    row = conn.execute(f"SELECT {_CATEGORY_COLUMNS} FROM categories WHERE id = ?", (category_id,)).fetchone()  # noqa: S608
    return _record(row, _CATEGORY_BOOLS) if row else None


# ------------------------------------------------------------ transactions


@dataclass(frozen=True)
class TransactionFilters:
    date_from: date | None = None
    date_to: date | None = None
    account_id: str | None = None
    category_id: str | None = None
    tax_section: str | None = None
    review_status: str | None = None
    q: str | None = None


def encode_cursor(tx_date: str, tx_id: str) -> str:
    return base64.urlsafe_b64encode(json.dumps([tx_date, tx_id]).encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[str, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        tx_date, tx_id = json.loads(raw)
        date.fromisoformat(tx_date)
    except (binascii.Error, ValueError, TypeError):
        raise ValueError("Invalid cursor.") from None
    if not isinstance(tx_id, str):
        raise ValueError("Invalid cursor.")
    return tx_date, tx_id


def _like_pattern(text: str) -> str:
    escaped = text.replace(_ESCAPE, _ESCAPE * 2).replace("%", _ESCAPE + "%").replace("_", _ESCAPE + "_")
    return f"%{escaped}%"


def _filter_clauses(f: TransactionFilters) -> tuple[list[str], list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    simple = (
        ("t.transaction_date >= ?", f.date_from.isoformat() if f.date_from else None),
        ("t.transaction_date <= ?", f.date_to.isoformat() if f.date_to else None),
        ("t.account_id = ?", f.account_id),
        ("t.category_id = ?", f.category_id),
        ("t.tax_section = ?", f.tax_section),
        ("t.review_status = ?", f.review_status),
    )
    for clause, value in simple:
        if value is not None:
            clauses.append(clause)
            params.append(value)
    if f.q:
        pattern = _like_pattern(f.q)
        clauses.append(
            f"(t.clean_description LIKE ? ESCAPE '{_ESCAPE}' OR t.description LIKE ? ESCAPE '{_ESCAPE}')"
        )
        params.extend([pattern, pattern])
    return clauses, params


def list_transactions(
    conn: sqlite3.Connection, filters: TransactionFilters, limit: int, cursor: str | None
) -> tuple[list[Record], str | None]:
    """Keyset page ordered by (transaction_date DESC, id DESC); returns (rows, next_cursor)."""
    clauses, params = _filter_clauses(filters)
    if cursor:
        cursor_date, cursor_id = decode_cursor(cursor)
        clauses.append("(t.transaction_date < ? OR (t.transaction_date = ? AND t.id < ?))")
        params.extend([cursor_date, cursor_date, cursor_id])
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"{_TX_SELECT}{where} ORDER BY t.transaction_date DESC, t.id DESC LIMIT ?",  # noqa: S608
        (*params, limit + 1),
    ).fetchall()
    page = [_record(r, ("is_verified",)) for r in rows[:limit]]
    next_cursor = None
    if len(rows) > limit:
        next_cursor = encode_cursor(page[-1]["transaction_date"], page[-1]["id"])
    return page, next_cursor


def get_transaction(conn: sqlite3.Connection, transaction_id: str) -> Record | None:
    row = conn.execute(f"{_TX_SELECT} WHERE t.id = ?", (transaction_id,)).fetchone()  # noqa: S608
    return _record(row, ("is_verified",)) if row else None


def apply_transaction_patch(
    conn: sqlite3.Connection,
    transaction_id: str,
    expected_version: int,
    changes: dict[str, Any],
    today: date,
) -> Record:
    """Apply notes / tax_section / category_id changes if the version still matches (atomic)."""
    with transaction(conn):
        current = get_transaction(conn, transaction_id)
        if current is None:
            raise ValueError("Unknown transaction.")
        if current["version"] != expected_version:
            raise VersionConflictError(current)
        if "category_id" in changes:
            LedgerService(conn).recategorize(
                transaction_id,
                changes["category_id"],
                today,
                f"recategorize:{transaction_id}:{expected_version}",
            )
        notes = changes.get("notes", current["notes"])
        tax_section = changes.get("tax_section", current["tax_section"])
        conn.execute(
            "UPDATE transactions SET notes = ?, tax_section = ?, version = version + 1, "
            "updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
            (notes, tax_section, transaction_id),
        )
    updated = get_transaction(conn, transaction_id)
    assert updated is not None
    return updated


def journal_entry_id_of(conn: sqlite3.Connection, transaction_id: str) -> str | None:
    row = conn.execute("SELECT journal_entry_id FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
    return row["journal_entry_id"] if row else None


# ------------------------------------------------------------------ splits


def list_splits(conn: sqlite3.Connection, status: str | None) -> list[Record]:
    where, params = ("WHERE s.status = ?", (status,)) if status else ("", ())
    rows = conn.execute(
        f"{_SPLIT_SELECT} {where} ORDER BY t.transaction_date DESC, s.id",  # noqa: S608
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_split(conn: sqlite3.Connection, split_id: str) -> Record | None:
    row = conn.execute(f"{_SPLIT_SELECT} WHERE s.id = ?", (split_id,)).fetchone()  # noqa: S608
    return dict(row) if row else None


# --------------------------------------------------------------- dashboard


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    return int(conn.execute(sql, params).fetchone()[0])


def _balance_sum(conn: sqlite3.Connection, account_class: str, subtypes: tuple[str, ...]) -> int:
    marks = ",".join("?" * len(subtypes))
    return _scalar(
        conn,
        "SELECT COALESCE(SUM(current_balance_minor), 0) FROM accounts "  # noqa: S608
        f"WHERE is_active = 1 AND account_class = ? AND account_subtype IN ({marks})",
        (account_class, *subtypes),
    )


def _due_rules_sum(conn: sqlite3.Connection, start: date, end: date) -> int:
    return _scalar(
        conn,
        "SELECT COALESCE(SUM(expected_amount_minor), 0) FROM recurring_rules WHERE is_active = 1 "
        "AND is_mandatory = 1 AND next_expected_date BETWEEN ? AND ?",
        (start.isoformat(), end.isoformat()),
    )


def _month_flow(conn: sqlite3.Connection, account_class: str, first: date, next_first: date) -> int:
    return _scalar(
        conn,
        "SELECT COALESCE(SUM(l.signed_amount_minor), 0) FROM journal_lines l "
        "JOIN journal_entries e ON e.id = l.journal_entry_id JOIN accounts a ON a.id = l.account_id "
        "WHERE e.status = 'POSTED' AND a.account_class = ? AND e.entry_date >= ? AND e.entry_date < ?",
        (account_class, first.isoformat(), next_first.isoformat()),
    )


def _upcoming_bills(conn: sqlite3.Connection, start: date, end: date) -> list[Record]:
    rows = conn.execute(
        "SELECT r.id, r.merchant_id, m.canonical_name AS merchant_name, r.category_id, "
        "r.expected_amount_minor, r.frequency, r.next_expected_date, r.is_mandatory "
        "FROM recurring_rules r JOIN merchants m ON m.id = r.merchant_id "
        "WHERE r.is_active = 1 AND r.next_expected_date BETWEEN ? AND ? "
        "ORDER BY r.next_expected_date, r.id",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return [_record(r, ("is_mandatory",)) for r in rows]


def dashboard_summary(conn: sqlite3.Connection, today: date) -> Record:
    last_day = calendar.monthrange(today.year, today.month)[1]
    days_remaining = last_day - today.day + 1
    first = today.replace(day=1)
    next_first = first.replace(day=last_day) + timedelta(days=1)
    safe = calculate_safe_to_spend_minor(
        _balance_sum(conn, "ASSET", LIQUID_SUBTYPES),
        _balance_sum(conn, "LIABILITY", ("CREDIT_CARD",)),
        _due_rules_sum(conn, today, today + timedelta(days=OBLIGATION_DAYS)),
        _scalar(
            conn,
            "SELECT COALESCE(SUM(current_locked_amount_minor), 0) FROM financial_goals "
            "WHERE status = 'ACTIVE'",
        ),
        days_remaining,
    )
    return {
        "as_of": today.isoformat(),
        "month": today.strftime("%Y-%m"),
        "safe_to_spend": {**asdict(safe), "days_remaining_in_month": days_remaining},
        "net_worth_minor": _scalar(
            conn,
            "SELECT COALESCE(SUM(current_balance_minor), 0) FROM accounts "
            "WHERE is_active = 1 AND account_class IN ('ASSET', 'LIABILITY')",
        ),
        "month_expense_minor": _month_flow(conn, "EXPENSE", first, next_first),
        "month_income_minor": -_month_flow(conn, "INCOME", first, next_first),
        "upcoming_bills": _upcoming_bills(conn, today, today + timedelta(days=UPCOMING_BILL_DAYS)),
        "pending_review_count": _scalar(
            conn, "SELECT COUNT(*) FROM transactions WHERE review_status = 'PENDING_REVIEW'"
        ),
    }
