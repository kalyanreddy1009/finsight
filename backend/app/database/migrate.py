"""Forward-only SQL migration runner."""

import re
import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_NAME_RE = re.compile(r"^\d{4}_[a-z0-9_]+\.sql$")
_COMMENT_RE = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)
# Only statements *starting* with these are transaction control; trigger bodies start with CREATE.
_TXN_CONTROL_RE = re.compile(r"^\s*(BEGIN|COMMIT|END|ROLLBACK|SAVEPOINT|RELEASE)\b", re.IGNORECASE)


class MigrationError(Exception):
    """A migration file is invalid or failed to apply."""


def _split_statements(script: str, name: str) -> list[str]:
    """Split a script into complete statements (sqlite3.complete_statement understands triggers)."""
    statements: list[str] = []
    buffer = ""
    for line in script.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statements.append(buffer)
            buffer = ""
    if _COMMENT_RE.sub("", buffer).strip():
        raise MigrationError(f"Migration {name} ends with an incomplete statement")
    return statements


def apply_migrations(conn: sqlite3.Connection, migrations_dir: Path | None = None) -> list[str]:
    """Apply pending migrations in order; return the versions applied by this call.

    Each migration runs, together with its schema_migrations row, in one BEGIN IMMEDIATE
    transaction and is rolled back entirely on any failure.
    """
    directory = migrations_dir or MIGRATIONS_DIR
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version TEXT PRIMARY KEY, "
        "applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))"
    )
    done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    applied: list[str] = []
    for path in sorted(p for p in directory.iterdir() if _NAME_RE.match(p.name)):
        version = path.stem
        if version in done:
            continue
        statements = _split_statements(path.read_text(encoding="utf-8"), path.name)
        for statement in statements:
            if _TXN_CONTROL_RE.match(_COMMENT_RE.sub("", statement)):
                raise MigrationError(
                    f"Migration {path.name} must not contain transaction-control statements; "
                    "the runner manages the transaction"
                )
        conn.execute("BEGIN IMMEDIATE")
        try:
            for statement in statements:
                conn.execute(statement)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        applied.append(version)
    return applied
