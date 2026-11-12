"""Statement ingestion: validate, dedupe, parse, verify balances, categorize and stage rows."""

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.database.session import transaction
from app.ingestion.base_parser import ParsedStatement, StatementParser
from app.ingestion.normalizer import (
    IndianBankingNormalizer,
    NormalizationResult,
    NormalizedTransactionCandidate,
)
from app.ingestion.rule_categorizer import categorize

MAX_FILE_BYTES = 25 * 1024 * 1024
AUTO_APPROVE_CONFIDENCE = 0.95
PROVISIONAL_WINDOW_DAYS = 3
STATEMENT_KINDS = ("BANK_PDF", "CARD_PDF", "CSV", "CAS_PDF")
_PDF_SIGNATURE = b"%PDF-1."
_EDITABLE_STATUSES = ("PENDING_REVIEW", "AUTO_APPROVED", "USER_APPROVED", "REJECTED")
_TARGET_STATUSES = ("PENDING_REVIEW", "USER_APPROVED", "REJECTED")


class StatementRejectedError(Exception):
    """The upload was refused; the message starts with an UPPER_SNAKE code."""


class DuplicateStatementError(Exception):
    def __init__(self, statement_id: str) -> None:
        super().__init__(f"DUPLICATE_STATEMENT: already imported as {statement_id}")
        self.statement_id = statement_id


class StatementNotFoundError(ValueError):
    pass


class RowNotFoundError(ValueError):
    pass


class InvalidRowUpdateError(ValueError):
    pass


@dataclass(frozen=True)
class IngestResult:
    statement_id: str
    processing_status: str
    row_count: int
    auto_approved_count: int
    pending_review_count: int
    duplicate_count: int
    mismatch_count: int
    reconciliation_diff_minor: int


@dataclass(frozen=True)
class StatementReview:
    statement: dict[str, Any]
    rows: tuple[dict[str, Any], ...]
    import_errors: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class _StagedRow:
    candidate: NormalizedTransactionCandidate
    page_number: int
    stated_balance_minor: int | None
    merchant_id: str | None
    category_id: str
    confidence: float
    status: str
    duplicate_of: str | None
    provisional_match: str | None


# ------------------------------------------------------------------ validation


def _validate_upload(conn: sqlite3.Connection, account_id: str, content: bytes, kind: str) -> None:
    if len(content) > MAX_FILE_BYTES:
        raise StatementRejectedError("FILE_TOO_LARGE: statement files are limited to 25 MB")
    if kind not in STATEMENT_KINDS:
        raise StatementRejectedError("UNSUPPORTED_STATEMENT_KIND: unknown statement kind")
    if not content.startswith(_PDF_SIGNATURE):
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            raise StatementRejectedError("UNSUPPORTED_FILE_TYPE: expected a PDF or UTF-8 text") from None
    account = conn.execute("SELECT is_active FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if account is None:
        raise StatementRejectedError("ACCOUNT_NOT_FOUND: unknown account")
    if not account["is_active"]:
        raise StatementRejectedError("ACCOUNT_INACTIVE: account is not active")


def _existing_statement_id(conn: sqlite3.Connection, sha256_hex: str) -> str | None:
    row = conn.execute("SELECT id FROM statements WHERE file_hash_sha256 = ?", (sha256_hex,)).fetchone()
    return None if row is None else row["id"]


def _known_fingerprint(conn: sqlite3.Connection, account_id: str, parser_name: str) -> str | None:
    row = conn.execute(
        "SELECT layout_fingerprint FROM statements WHERE account_id = ? AND parser_name = ? "
        "AND processing_status = 'APPROVED' "
        "ORDER BY statement_end_date DESC, approved_at DESC, id DESC LIMIT 1",
        (account_id, parser_name),
    ).fetchone()
    return None if row is None else row["layout_fingerprint"]


# ------------------------------------------------------------- row classification


def _find_duplicate(
    conn: sqlite3.Connection, account_id: str, c: NormalizedTransactionCandidate
) -> str | None:
    row = conn.execute(
        "SELECT id FROM transactions WHERE account_id = ? "
        "AND review_status NOT IN ('SUPERSEDED', 'PROVISIONAL') "
        "AND ((? IS NOT NULL AND external_reference = ?) OR dedup_fingerprint = ?) "
        "ORDER BY transaction_date, id LIMIT 1",
        (account_id, c.external_utr, c.external_utr, c.dedup_fingerprint),
    ).fetchone()
    return None if row is None else row["id"]


def _find_provisional(
    conn: sqlite3.Connection, account_id: str, c: NormalizedTransactionCandidate, claimed: set[str]
) -> str | None:
    rows = conn.execute(
        "SELECT id, transaction_date, external_reference FROM transactions WHERE account_id = ? "
        "AND review_status = 'PROVISIONAL' AND direction = ? AND amount_minor = ?",
        (account_id, c.direction, c.amount_minor),
    ).fetchall()
    best: tuple[int, str] | None = None
    for row in rows:
        if row["id"] in claimed:
            continue
        gap = abs((date.fromisoformat(row["transaction_date"]) - c.tx_date).days)
        same_ref = c.external_utr is not None and row["external_reference"] == c.external_utr
        if (gap <= PROVISIONAL_WINDOW_DAYS or same_ref) and (best is None or (gap, row["id"]) < best):
            best = (gap, row["id"])
    return None if best is None else best[1]


def _stage_rows(
    conn: sqlite3.Connection,
    account_id: str,
    parsed: ParsedStatement,
    result: NormalizationResult,
    reconciled: bool,
) -> list[_StagedRow]:
    claimed: set[str] = set()
    staged: list[_StagedRow] = []
    for raw, c in zip(parsed.rows, result.candidates, strict=True):
        duplicate_of = _find_duplicate(conn, account_id, c)
        match = categorize(
            conn,
            clean_description=c.clean_description,
            extracted_vpa=c.extracted_vpa,
            direction=c.direction,
        )
        provisional = None if duplicate_of else _find_provisional(conn, account_id, c, claimed)
        if provisional:
            claimed.add(provisional)
        auto = match.confidence >= AUTO_APPROVE_CONFIDENCE and c.balance_verified and reconciled
        status = "DUPLICATE" if duplicate_of else ("AUTO_APPROVED" if auto else "PENDING_REVIEW")
        staged.append(
            _StagedRow(
                c,
                raw.page_number,
                raw.stated_running_balance_minor,
                match.merchant_id,
                match.category_id,
                match.confidence,
                status,
                duplicate_of,
                provisional,
            )  # fmt: skip
        )
    return staged


# ----------------------------------------------------------------------- writes


def _insert_statement(
    conn: sqlite3.Connection,
    ids: tuple[str, str],
    kind: str,
    filename: str,
    file_info: tuple[str, str],
    parsed: ParsedStatement,
    computed: int,
) -> None:
    statement_id, account_id = ids
    sha, path = file_info
    conn.execute(
        "INSERT INTO statements (id, account_id, statement_kind, original_filename, file_hash_sha256, "
        "layout_fingerprint, parser_name, parser_version, storage_path, statement_start_date, "
        "statement_end_date, opening_balance_minor, closing_balance_minor, computed_closing_minor, "
        "reconciliation_diff_minor, processing_status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'REVIEW_REQUIRED')",
        (
            statement_id, account_id, kind, filename, sha, parsed.layout_fingerprint, parsed.parser_name,
            parsed.parser_version, path, parsed.statement_start_date.isoformat(),
            parsed.statement_end_date.isoformat(), parsed.opening_balance_minor,
            parsed.closing_balance_minor, computed, computed - parsed.closing_balance_minor,
        ),
    )  # fmt: skip


def _insert_rows(conn: sqlite3.Connection, statement_id: str, staged: Sequence[_StagedRow]) -> None:
    for s in staged:
        c = s.candidate
        conn.execute(
            "INSERT INTO statement_rows (id, statement_id, row_index, page_number, tx_date, "
            "raw_description, clean_description, channel, extracted_vpa, external_reference, "
            "dedup_fingerprint, amount_minor, direction, stated_balance_minor, balance_verified, "
            "merchant_id, suggested_category_id, confidence_score, row_status, "
            "duplicate_of_transaction_id, provisional_match_transaction_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()), statement_id, c.row_index, s.page_number, c.tx_date.isoformat(),
                c.raw_description, c.clean_description, c.channel, c.extracted_vpa, c.external_utr,
                c.dedup_fingerprint, c.amount_minor, c.direction, s.stated_balance_minor,
                int(c.balance_verified), s.merchant_id, s.category_id, s.confidence, s.status,
                s.duplicate_of, s.provisional_match,
            ),
        )  # fmt: skip


def _insert_mismatches(
    conn: sqlite3.Connection, statement_id: str, parsed: ParsedStatement, result: NormalizationResult
) -> None:
    raws = {r.row_index: r for r in parsed.rows}
    for m in result.mismatches:
        raw = raws[m.row_index]
        conn.execute(
            "INSERT INTO import_errors (id, statement_id, page_number, row_index, raw_row_text, "
            "error_code, error_message, expected_running_balance_minor, actual_running_balance_minor) "
            "VALUES (?, ?, ?, ?, ?, 'RUNNING_BALANCE_MISMATCH', ?, ?, ?)",
            (
                str(uuid.uuid4()), statement_id, raw.page_number, m.row_index, raw.raw_description,
                f"Running balance does not match the stated balance at row {m.row_index}",
                m.expected_minor, m.stated_minor,
            ),
        )  # fmt: skip


def _audit(conn: sqlite3.Connection, statement_id: str, metadata: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO audit_events (id, event_type, target_object_type, target_object_id, metadata_json) "
        "VALUES (?, 'STATEMENT_UPLOADED', 'statement', ?, ?)",
        (str(uuid.uuid4()), statement_id, json.dumps(metadata, sort_keys=True)),
    )


def _count(staged: Sequence[_StagedRow], status: str) -> int:
    return sum(1 for r in staged if r.status == status)


def ingest_statement(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    filename: str,
    content: bytes,
    statement_kind: str,
    parsers: Sequence[StatementParser],
    document_store: Any,
    verify_layout: Callable[[str | None, str], None],
) -> IngestResult:
    _validate_upload(conn, account_id, content, statement_kind)
    sha = hashlib.sha256(content).hexdigest()
    if (existing := _existing_statement_id(conn, sha)) is not None:
        raise DuplicateStatementError(existing)
    parser = next((p for p in parsers if p.can_parse(content, filename)), None)
    if parser is None:
        raise StatementRejectedError("NO_PARSER: no parser recognises this statement")
    parsed = parser.parse(content, filename)
    verify_layout(_known_fingerprint(conn, account_id, parsed.parser_name), parsed.layout_fingerprint)
    result = IndianBankingNormalizer.normalize_and_verify_rows(
        account_id, parsed.opening_balance_minor, parsed.closing_balance_minor, list(parsed.rows)
    )
    diff = result.final_computed_balance_minor - parsed.closing_balance_minor
    staged = _stage_rows(conn, account_id, parsed, result, not result.mismatches and diff == 0)
    statement_id = str(uuid.uuid4())
    try:
        with transaction(conn):
            path = document_store.save(content, sha)
            _insert_statement(
                conn, (statement_id, account_id), statement_kind, filename, (sha, path), parsed,
                result.final_computed_balance_minor,
            )  # fmt: skip
            _insert_rows(conn, statement_id, staged)
            _insert_mismatches(conn, statement_id, parsed, result)
            _audit(conn, statement_id, {"rows": len(staged), "kind": statement_kind})
    except sqlite3.IntegrityError:
        if (existing := _existing_statement_id(conn, sha)) is not None:
            raise DuplicateStatementError(existing) from None
        raise
    return IngestResult(
        statement_id, "REVIEW_REQUIRED", len(staged), _count(staged, "AUTO_APPROVED"),
        _count(staged, "PENDING_REVIEW"), _count(staged, "DUPLICATE"), len(result.mismatches), diff,
    )  # fmt: skip


# ------------------------------------------------------------------ review API

_SUMMARY_SQL = (
    "SELECT id, account_id, statement_kind, original_filename, parser_name, parser_version, "
    "statement_start_date, statement_end_date, opening_balance_minor, closing_balance_minor, "
    "computed_closing_minor, reconciliation_diff_minor, processing_status, uploaded_at, approved_at "
    "FROM statements WHERE id = ?"
)


def get_review(conn: sqlite3.Connection, statement_id: str) -> StatementReview:
    stmt = conn.execute(_SUMMARY_SQL, (statement_id,)).fetchone()
    if stmt is None:
        raise StatementNotFoundError("Unknown statement.")
    rows = conn.execute(
        "SELECT * FROM statement_rows WHERE statement_id = ? ORDER BY row_index", (statement_id,)
    ).fetchall()
    errors = conn.execute(
        "SELECT * FROM import_errors WHERE statement_id = ? ORDER BY row_index, id", (statement_id,)
    ).fetchall()
    return StatementReview(dict(stmt), tuple(dict(r) for r in rows), tuple(dict(e) for e in errors))


def update_row(
    conn: sqlite3.Connection,
    row_id: str,
    *,
    row_status: str | None = None,
    suggested_category_id: str | None = None,
) -> None:
    """Review a staged row: approve, reject or re-queue it, and/or change its category."""
    if row_status is None and suggested_category_id is None:
        raise InvalidRowUpdateError("Nothing to update.")
    if row_status is not None and row_status not in _TARGET_STATUSES:
        raise InvalidRowUpdateError("Row status cannot be set to that value.")
    with transaction(conn):
        row = conn.execute(
            "SELECT r.id, r.row_status, r.direction, s.processing_status FROM statement_rows r "
            "JOIN statements s ON s.id = r.statement_id WHERE r.id = ?",
            (row_id,),
        ).fetchone()
        if row is None:
            raise RowNotFoundError("Unknown statement row.")
        if row["processing_status"] != "REVIEW_REQUIRED" or row["row_status"] not in _EDITABLE_STATUSES:
            raise InvalidRowUpdateError("This row can no longer be changed.")
        if suggested_category_id is not None:
            _check_category(conn, suggested_category_id, row["direction"])
            conn.execute(
                "UPDATE statement_rows SET suggested_category_id = ? WHERE id = ?",
                (suggested_category_id, row_id),
            )
        if row_status is not None:
            conn.execute("UPDATE statement_rows SET row_status = ? WHERE id = ?", (row_status, row_id))


def _check_category(conn: sqlite3.Connection, category_id: str, direction: str) -> None:
    cat = conn.execute("SELECT category_type FROM categories WHERE id = ?", (category_id,)).fetchone()
    expected = "INCOME" if direction == "CREDIT" else "EXPENSE"
    if cat is None or cat["category_type"] != expected:
        raise InvalidRowUpdateError(f"Category must exist and be of type {expected}.")
