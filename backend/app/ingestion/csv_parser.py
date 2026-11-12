"""Generic CSV bank-statement parser: UTF-8, day-first dates, debit/credit or a single signed amount column.

Pure logic: no database access and no file-system access.
"""

import csv
import io
import re
from dataclasses import dataclass, replace
from datetime import date, datetime

from app.core.money import to_minor
from app.ingestion.base_parser import ParsedStatement, StatementParseError
from app.ingestion.drift_guard import compute_layout_fingerprint, normalise_header_name
from app.ingestion.normalizer import RawParsedRow

MAX_DATA_ROWS = 20_000
MAX_ROW_AMOUNT_MINOR = 10**15
CSV_SUFFIX = ".csv"
PAGE_NUMBER = 1

_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("date", "txn date", "transaction date", "value date"),
    "description": ("description", "narration", "particulars", "remarks"),
    "debit": ("debit", "withdrawal", "withdrawal amt", "dr"),
    "credit": ("credit", "deposit", "deposit amt", "cr"),
    "balance": ("balance", "closing balance", "running balance"),
    "amount": ("amount",),
}
_ALIAS_TO_COLUMN: dict[str, str] = {
    alias: column for column, aliases in _COLUMN_ALIASES.items() for alias in aliases
}
_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y", "%d %b %Y", "%d/%m/%y")
_CURRENCY_PREFIX_RE = re.compile(r"^(?:₹|INR|Rs\.?)\s*", re.IGNORECASE)
_DR_CR_SUFFIX_RE = re.compile(r"\s*(?:Cr|Dr)\.?$", re.IGNORECASE)


@dataclass(frozen=True)
class _ColumnLayout:
    date_index: int
    description_index: int
    debit_index: int | None
    credit_index: int | None
    amount_index: int | None
    balance_index: int | None


def _read_table(content: bytes) -> list[list[str]]:
    """Returns the non-blank CSV records of the file; the first one is the header row."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise StatementParseError("CSV_ENCODING: the file is not valid UTF-8") from exc
    try:
        records = list(csv.reader(io.StringIO(text, newline="")))
    except csv.Error as exc:
        raise StatementParseError("CSV_MALFORMED: the file is not valid CSV") from exc
    table = [record for record in records if any(cell.strip() for cell in record)]
    if not table:
        raise StatementParseError("CSV_NO_HEADER: the file has no header row")
    return table


def _map_columns(headers: list[str]) -> dict[str, int]:
    columns: dict[str, int] = {}
    for index, header in enumerate(headers):
        column = _ALIAS_TO_COLUMN.get(header)
        if column is not None and column not in columns:
            columns[column] = index
    return columns


def _resolve_layout(headers: list[str]) -> _ColumnLayout:
    columns = _map_columns(headers)
    for required in ("date", "description"):
        if required not in columns:
            accepted = ", ".join(_COLUMN_ALIASES[required])
            raise StatementParseError(f"CSV_MISSING_COLUMN: no {required} column (accepted: {accepted})")
    has_split_amounts = "debit" in columns and "credit" in columns
    if not has_split_amounts and "amount" not in columns:
        raise StatementParseError(
            "CSV_MISSING_COLUMN: need both debit and credit columns, or an amount column"
        )
    return _ColumnLayout(
        date_index=columns["date"],
        description_index=columns["description"],
        debit_index=columns.get("debit") if has_split_amounts else None,
        credit_index=columns.get("credit") if has_split_amounts else None,
        amount_index=None if has_split_amounts else columns["amount"],
        balance_index=columns.get("balance"),
    )


def _cell(cells: list[str], index: int | None) -> str:
    if index is None or index >= len(cells):
        return ""
    return cells[index].strip()


def _parse_date(text: str, row_number: int) -> date:
    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    raise StatementParseError(f"CSV_BAD_DATE: data row {row_number} has an unparseable date")


def _parse_amount(text: str, column: str, row_number: int) -> int:
    """Returns signed paise; an empty cell is 0."""
    cleaned = text.strip()
    if not cleaned:
        return 0
    cleaned = _CURRENCY_PREFIX_RE.sub("", cleaned)
    cleaned = _DR_CR_SUFFIX_RE.sub("", cleaned)
    cleaned = cleaned.replace(",", "").replace(" ", "")
    try:
        amount_minor = to_minor(cleaned)
    except ValueError as exc:
        raise StatementParseError(
            f"CSV_BAD_AMOUNT: data row {row_number} has an invalid {column} amount"
        ) from exc
    if abs(amount_minor) > MAX_ROW_AMOUNT_MINOR:
        raise StatementParseError(
            f"CSV_BAD_AMOUNT: data row {row_number} has a {column} amount above the supported limit"
        )
    return amount_minor


def _row_amounts(cells: list[str], layout: _ColumnLayout, row_number: int) -> tuple[int, int]:
    """Returns (debit_minor, credit_minor), both non-negative."""
    if layout.amount_index is None:
        debit = _parse_amount(_cell(cells, layout.debit_index), "debit", row_number)
        credit = _parse_amount(_cell(cells, layout.credit_index), "credit", row_number)
        if debit < 0 or credit < 0:
            raise StatementParseError(f"CSV_BAD_AMOUNT: data row {row_number} has a negative debit or credit")
        return debit, credit
    signed = _parse_amount(_cell(cells, layout.amount_index), "amount", row_number)
    if signed < 0:
        return -signed, 0
    return 0, signed


def _row_balance(cells: list[str], layout: _ColumnLayout, row_number: int) -> int | None:
    text = _cell(cells, layout.balance_index)
    if not text:
        return None
    return _parse_amount(text, "balance", row_number)


def _parse_row(cells: list[str], layout: _ColumnLayout, row_number: int) -> RawParsedRow:
    tx_date = _parse_date(_cell(cells, layout.date_index), row_number)
    debit, credit = _row_amounts(cells, layout, row_number)
    if (debit > 0) == (credit > 0):
        raise StatementParseError(
            f"CSV_BAD_ROW_AMOUNT: data row {row_number} must have exactly one of debit or credit above zero"
        )
    return RawParsedRow(
        row_index=row_number - 1,
        page_number=PAGE_NUMBER,
        tx_date=tx_date,
        raw_description=_cell(cells, layout.description_index),
        debit_minor=debit,
        credit_minor=credit,
        stated_running_balance_minor=_row_balance(cells, layout, row_number),
    )


def _chronological(rows: list[RawParsedRow]) -> list[RawParsedRow]:
    """Reverses the rows when the file runs newest-first; re-indexes them from 0."""
    dates = [row.tx_date for row in rows]
    descending = all(earlier >= later for earlier, later in zip(dates, dates[1:], strict=False))
    ordered = rows[::-1] if descending and dates[0] > dates[-1] else rows
    return [replace(row, row_index=index) for index, row in enumerate(ordered)]


def _balances(rows: list[RawParsedRow]) -> tuple[int, int]:
    first, last = rows[0], rows[-1]
    if first.stated_running_balance_minor is not None:
        opening = first.stated_running_balance_minor - first.credit_minor + first.debit_minor
    else:
        opening = 0
    if last.stated_running_balance_minor is not None:
        return opening, last.stated_running_balance_minor
    closing = opening + sum(row.credit_minor for row in rows) - sum(row.debit_minor for row in rows)
    return opening, closing


class GenericCsvParser:
    name = "generic_csv"
    version = "1"

    def can_parse(self, content: bytes, filename: str) -> bool:
        if not filename.lower().endswith(CSV_SUFFIX):
            return False
        try:
            table = _read_table(content)
            _resolve_layout(_normalised_headers(table[0]))
        except StatementParseError:
            return False
        return True

    def parse(self, content: bytes, filename: str) -> ParsedStatement:
        table = _read_table(content)
        headers = _normalised_headers(table[0])
        layout = _resolve_layout(headers)
        data_records = table[1:]
        if len(data_records) > MAX_DATA_ROWS:
            raise StatementParseError(
                f"CSV_TOO_MANY_ROWS: {len(data_records)} data rows exceed the limit of {MAX_DATA_ROWS}"
            )
        if not data_records:
            raise StatementParseError("CSV_NO_ROWS: the statement has no transaction rows")
        rows = _chronological(
            [_parse_row(cells, layout, number) for number, cells in enumerate(data_records, start=1)]
        )
        opening, closing = _balances(rows)
        dates = [row.tx_date for row in rows]
        return ParsedStatement(
            parser_name=self.name,
            parser_version=self.version,
            institution=None,
            account_number_masked=None,
            statement_start_date=min(dates),
            statement_end_date=max(dates),
            opening_balance_minor=opening,
            closing_balance_minor=closing,
            layout_fingerprint=compute_layout_fingerprint(headers, None),
            rows=tuple(rows),
        )


def _normalised_headers(header_cells: list[str]) -> list[str]:
    return [normalise_header_name(cell) for cell in header_cells]
