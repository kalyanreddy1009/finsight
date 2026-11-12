"""Forward-only SQL migration runner."""

import re
import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_NAME_RE = re.compile(r"^(\d{4})_.+\.sql$")


def apply_migrations(conn: sqlite3.Connection) -> list[str]:
    """Apply pending migrations in order; return the versions applied by this call."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version TEXT PRIMARY KEY, "
        "applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))"
    )
    done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    applied: list[str] = []
    for path in sorted(p for p in MIGRATIONS_DIR.iterdir() if _NAME_RE.match(p.name)):
        version = path.stem
        if version in done:
            continue
        script = path.read_text(encoding="utf-8")
        # executescript handles semicolons inside trigger bodies. Wrap the script and the
        # bookkeeping insert in one explicit transaction so each migration is atomic.
        try:
            conn.executescript(
                "BEGIN IMMEDIATE;\n"
                + script
                + f"\nINSERT INTO schema_migrations (version) VALUES ('{version}');\nCOMMIT;"
            )
        except sqlite3.Error:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        applied.append(version)
    return applied
