"""SQLite/SQLCipher connection helpers."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

from app.core.config import get_settings

# recursive_triggers makes INSERT OR REPLACE fire the DELETE triggers for the row it replaces.
_PRAGMAS = (
    "PRAGMA foreign_keys = ON",
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = FULL",
    "PRAGMA temp_store = MEMORY",
    "PRAGMA recursive_triggers = ON",
)


def _quote_key(key: str) -> str:
    return "'" + key.replace("'", "''") + "'"


def _open_sqlcipher(db_path: str | Path, key: str | None) -> sqlite3.Connection:
    if key is not None and "\x00" in key:
        raise ValueError("Database key must not contain NUL characters")
    from sqlcipher3 import dbapi2 as driver  # noqa: PLC0415

    conn = driver.connect(str(db_path), isolation_level=None)
    if key is not None:
        conn.execute(f"PRAGMA key = {_quote_key(key)}")
        try:
            conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        except Exception:
            conn.close()
            # Deliberately not chained, so nothing key-related can leak via the traceback.
            raise RuntimeError("Unable to open encrypted database: wrong key or corrupt file") from None
    return conn


def connect(db_path: str | Path, key: str | None = None) -> sqlite3.Connection:
    """Open a connection with explicit transactions and the standard PRAGMAs applied."""
    if get_settings().db_driver == "sqlcipher":
        conn = _open_sqlcipher(db_path, key)
    else:
        conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    for pragma in _PRAGMAS:
        conn.execute(pragma)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """BEGIN IMMEDIATE ... COMMIT, rolling back on any exception.

    Nesting is not supported: calling this while a transaction is open raises sqlite3.OperationalError.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            # A failed rollback must never mask the original exception.
            with suppress(sqlite3.Error):
                conn.execute("ROLLBACK")
        raise
