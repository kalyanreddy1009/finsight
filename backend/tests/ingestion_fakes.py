"""Shared stand-ins and builders for the ingestion pipeline tests."""

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import date

from app.finance import chart
from app.finance.ledger_service import LedgerService
from app.ingestion.base_parser import ParsedStatement
from app.ingestion.drift_guard import verify_layout
from app.ingestion.normalizer import RawParsedRow
from app.ingestion.pipeline import IngestResult, ingest_statement

__all__ = ["verify_layout"]

LAYOUT = "layout-a"


@dataclass
class FakeParser:
    parsed: ParsedStatement
    accepts: bool = True
    name: str = "fake"
    version: str = "1"

    def can_parse(self, content: bytes, filename: str) -> bool:
        return self.accepts

    def parse(self, content: bytes, filename: str) -> ParsedStatement:
        return self.parsed


@dataclass
class InMemoryDocumentStore:
    saved: dict[str, bytes] = field(default_factory=dict)

    def save(self, content: bytes, sha256_hex: str) -> str:
        self.saved[sha256_hex] = content
        return f"{sha256_hex[:2]}/{sha256_hex}.bin"


def upi(utr: str, merchant: str, vpa: str) -> str:
    return f"UPI/DR/{utr}/{merchant}/YESB0000001/{vpa}"


def make_statement(
    rows: list[tuple[date, str, int, int]],
    *,
    opening: int = 100_000,
    closing: int | None = None,
    fingerprint: str = LAYOUT,
    start: date = date(2026, 3, 1),
    end: date = date(2026, 3, 31),
    stated_overrides: dict[int, int] | None = None,
) -> ParsedStatement:
    """Rows are (date, narration, debit, credit); balances are derived unless overridden."""
    balance = opening
    raw: list[RawParsedRow] = []
    for index, (tx_date, text, debit, credit) in enumerate(rows, start=1):
        balance += credit - debit
        stated = (stated_overrides or {}).get(index, balance)
        raw.append(RawParsedRow(index, 1, tx_date, text, debit, credit, stated))
    return ParsedStatement(
        parser_name="fake",
        parser_version="1",
        institution="Test Bank",
        account_number_masked="XXXX1234",
        statement_start_date=start,
        statement_end_date=end,
        opening_balance_minor=opening,
        closing_balance_minor=balance if closing is None else closing,
        layout_fingerprint=fingerprint,
        rows=tuple(raw),
    )


def make_account(conn: sqlite3.Connection, name: str = "Savings") -> str:
    return chart.create_account(conn, name=name, account_class="ASSET", account_subtype="BANK_SAVINGS")


def add_merchant(
    conn: sqlite3.Connection,
    name: str,
    category_id: str | None,
    *,
    vpas: list[str] | None = None,
    aliases: list[str] | None = None,
) -> str:
    merchant_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO merchants (id, canonical_name, upi_vpa_patterns, aliases_json, default_category_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (merchant_id, name, json.dumps(vpas or []), json.dumps(aliases or []), category_id),
    )
    return merchant_id


def ingest(
    conn: sqlite3.Connection,
    account_id: str,
    parsed: ParsedStatement,
    store: InMemoryDocumentStore,
    *,
    content: bytes | None = None,
    verify=verify_layout,
) -> IngestResult:
    return ingest_statement(
        conn,
        account_id=account_id,
        filename="stmt.csv",
        content=content if content is not None else f"csv-{uuid.uuid4()}".encode(),
        statement_kind="CSV",
        parsers=[FakeParser(parsed)],
        document_store=store,
        verify_layout=verify,
    )


def add_provisional(
    conn: sqlite3.Connection,
    account_id: str,
    category_id: str,
    amount: int,
    tx_date: date,
    *,
    key: str,
    external_reference: str | None = None,
) -> str:
    return LedgerService(conn).record_expense(
        source_account_id=account_id,
        category_id=category_id,
        amount_minor=amount,
        tx_date=tx_date,
        idempotency_key=key,
        external_reference=external_reference,
        is_provisional=True,
    )
