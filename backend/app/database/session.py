"""SQLite/SQLCipher connection helpers."""

import sqlite3
import uuid
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
def _savepoint(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Nested block inside an open transaction: RELEASE on success, ROLLBACK TO on any exception."""
    name = f"sp_{uuid.uuid4().hex}"
    conn.execute(f"SAVEPOINT {name}")
    try:
        yield conn
    except BaseException:
        # A failed rollback must never mask the original exception.
        with suppress(sqlite3.Error):
            conn.execute(f"ROLLBACK TO {name}")
        with suppress(sqlite3.Error):
            conn.execute(f"RELEASE {name}")
        raise
    conn.execute(f"RELEASE {name}")


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """BEGIN IMMEDIATE ... COMMIT, rolling back on any exception.

    If a transaction is already open on this connection, the block runs under a savepoint: its
    writes are released on success, or undone on any exception. The exception still propagates,
    and the outermost block decides whether anything is committed. A caller that catches the
    exception outside the inner block keeps the outer transaction's other writes.
    """
    if conn.in_transaction:
        with _savepoint(conn):
            yield conn
        return
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
