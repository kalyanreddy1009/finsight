"""SQLite/SQLCipher connection helpers."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.core.config import get_settings

_PRAGMAS = (
    "PRAGMA foreign_keys = ON",
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = FULL",
    "PRAGMA temp_store = MEMORY",
)


def _quote_key(key: str) -> str:
    return "'" + key.replace("'", "''") + "'"


def connect(db_path: str | Path, key: str | None = None) -> sqlite3.Connection:
    """Open a connection with explicit transactions and the standard PRAGMAs applied."""
    if get_settings().db_driver == "sqlcipher":
        from sqlcipher3 import dbapi2 as driver  # noqa: PLC0415

        conn = driver.connect(str(db_path), isolation_level=None)
        if key is not None:
            conn.execute(f"PRAGMA key = {_quote_key(key)}")
    else:
        conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    for pragma in _PRAGMAS:
        conn.execute(pragma)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """BEGIN IMMEDIATE ... COMMIT, rolling back on any exception."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
