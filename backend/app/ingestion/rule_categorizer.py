"""Rule-based merchant and category matcher (exact VPA, then alias substring/regex)."""

import json
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from app.database import seed

VPA_CONFIDENCE = 0.99
ALIAS_CONFIDENCE = 0.96
MAX_PATTERN_LENGTH = 200
MAX_MATCH_TEXT_LENGTH = 200
REGEX_PREFIX = "re:"
# A quantified group such as (a+)+ can backtrack catastrophically; such patterns are never run.
_QUANTIFIED_GROUP = re.compile(r"\)\s*[+*{]")


@dataclass(frozen=True)
class CategoryMatch:
    merchant_id: str | None
    category_id: str
    confidence: float
    stage: str  # 'VPA' | 'ALIAS' | 'NONE'


def _uncategorized_id(direction: str) -> str:
    if direction == "CREDIT":
        return seed.UNCATEGORIZED_INCOME_CATEGORY_ID
    return seed.UNCATEGORIZED_EXPENSE_CATEGORY_ID


def _json_strings(raw: str | None) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, str) and item]


def _alias_matches(alias: str, description: str) -> bool:
    if alias.startswith(REGEX_PREFIX):
        pattern = alias[len(REGEX_PREFIX) :]
        if not pattern or len(pattern) > MAX_PATTERN_LENGTH or _QUANTIFIED_GROUP.search(pattern):
            return False
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return False
        return compiled.search(description[:MAX_MATCH_TEXT_LENGTH]) is not None
    return alias.lower() in description.lower()


def _usable_category(conn: sqlite3.Connection, category_id: str | None, direction: str) -> str | None:
    """Return the category id only if it can be posted for this direction."""
    if category_id is None:
        return None
    expected = "INCOME" if direction == "CREDIT" else "EXPENSE"
    row = conn.execute("SELECT category_type FROM categories WHERE id = ?", (category_id,)).fetchone()
    if row is None or row["category_type"] != expected:
        return None
    return category_id


def _result(
    conn: sqlite3.Connection, merchant: sqlite3.Row, direction: str, confidence: float, stage: str
) -> CategoryMatch:
    category_id = _usable_category(conn, merchant["default_category_id"], direction)
    if category_id is None:
        return CategoryMatch(merchant["id"], _uncategorized_id(direction), 0.0, stage)
    return CategoryMatch(merchant["id"], category_id, confidence, stage)


def load_merchants(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Merchants in deterministic matching order; load once and pass to ``categorize``."""
    return conn.execute(
        "SELECT id, upi_vpa_patterns, aliases_json, default_category_id FROM merchants "
        "ORDER BY canonical_name, id"
    ).fetchall()


def categorize(
    conn: sqlite3.Connection,
    *,
    clean_description: str,
    extracted_vpa: str | None,
    direction: str,
    merchants: Sequence[sqlite3.Row] | None = None,
) -> CategoryMatch:
    """Match a row to a merchant/category; fall back to Uncategorized with confidence 0.0."""
    if merchants is None:
        merchants = load_merchants(conn)
    if extracted_vpa:
        vpa = extracted_vpa.lower()
        for merchant in merchants:
            if vpa in (p.lower() for p in _json_strings(merchant["upi_vpa_patterns"])):
                return _result(conn, merchant, direction, VPA_CONFIDENCE, "VPA")
    for merchant in merchants:
        if any(_alias_matches(a, clean_description) for a in _json_strings(merchant["aliases_json"])):
            return _result(conn, merchant, direction, ALIAS_CONFIDENCE, "ALIAS")
    return CategoryMatch(None, _uncategorized_id(direction), 0.0, "NONE")
