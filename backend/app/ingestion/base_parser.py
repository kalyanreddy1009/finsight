"""Statement parser interface shared by every statement format parser.

Pure logic: no database access and no file-system access.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.ingestion.normalizer import RawParsedRow


class StatementParseError(Exception):
    """Raised when a statement cannot be parsed.

    The message starts with an UPPER_SNAKE code, for example "CSV_MISSING_COLUMN: ...".
    """


@dataclass(frozen=True)
class ParsedStatement:
    parser_name: str
    parser_version: str
    institution: str | None
    account_number_masked: str | None
    statement_start_date: date
    statement_end_date: date
    opening_balance_minor: int
    closing_balance_minor: int
    layout_fingerprint: str
    rows: tuple[RawParsedRow, ...]


class StatementParser(Protocol):
    name: str
    version: str

    def can_parse(self, content: bytes, filename: str) -> bool: ...

    def parse(self, content: bytes, filename: str) -> ParsedStatement: ...
