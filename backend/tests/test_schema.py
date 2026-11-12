import sqlite3

import pytest

from app.database.migrate import apply_migrations
from app.database.seed import (
    OPENING_EQUITY_ACCOUNT_ID,
    PENDING_REIMBURSEMENTS_ACCOUNT_ID,
    seed_system_accounts,
)
from app.database.session import connect, transaction

ACCOUNT_A = OPENING_EQUITY_ACCOUNT_ID
ACCOUNT_B = PENDING_REIMBURSEMENTS_ACCOUNT_ID


def make_entry(conn, entry_id="e1", amounts=(100, -100), provisional=0):
    conn.execute(
        "INSERT INTO journal_entries (id, entry_date, entry_type, is_provisional, idempotency_key) "
        "VALUES (?, '2026-01-01', 'STANDARD', ?, ?)",
        (entry_id, provisional, f"key-{entry_id}"),
    )
    for i, amt in enumerate(amounts):
        conn.execute(
            "INSERT INTO journal_lines (id, journal_entry_id, account_id, signed_amount_minor) "
            "VALUES (?, ?, ?, ?)",
            (f"{entry_id}-l{i}", entry_id, ACCOUNT_A if i % 2 == 0 else ACCOUNT_B, amt),
        )
    return entry_id


def post(conn, entry_id):
    conn.execute("UPDATE journal_entries SET status = 'POSTED' WHERE id = ?", (entry_id,))


def status(conn, entry_id):
    return conn.execute("SELECT status FROM journal_entries WHERE id = ?", (entry_id,)).fetchone()[0]


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_apply_migrations_is_idempotent(conn):
    second = apply_migrations(conn)
    versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations")]
    assert second == []
    assert versions == ["0001_initial"]


def test_first_migration_run_reports_applied_versions(tmp_path):
    c = connect(tmp_path / "x.db")
    try:
        assert apply_migrations(c) == ["0001_initial"]
    finally:
        c.close()


def test_seed_system_accounts_is_idempotent(conn):
    seed_system_accounts(conn)
    assert conn.execute("SELECT COUNT(*) FROM accounts WHERE id LIKE 'sys-%'").fetchone()[0] == 2


def test_two_line_balanced_entry_posts(conn):
    make_entry(conn, amounts=(500, -500))
    post(conn, "e1")
    assert status(conn, "e1") == "POSTED"


def test_three_line_balanced_entry_posts(conn):
    make_entry(conn, amounts=(500, -300, -200))
    post(conn, "e1")
    assert status(conn, "e1") == "POSTED"


def test_unbalanced_entry_refuses_to_post(conn):
    make_entry(conn, amounts=(500, -300))
    with pytest.raises(sqlite3.IntegrityError, match="LEDGER_INTEGRITY_ERROR"):
        post(conn, "e1")
    assert status(conn, "e1") == "DRAFT"


def test_single_line_entry_refuses_to_post(conn):
    make_entry(conn, amounts=(500,))
    with pytest.raises(sqlite3.IntegrityError, match="LEDGER_INTEGRITY_ERROR"):
        post(conn, "e1")


def test_entry_cannot_be_inserted_as_posted(conn):
    with pytest.raises(sqlite3.IntegrityError, match="LEDGER_INTEGRITY_ERROR"):
        conn.execute(
            "INSERT INTO journal_entries (id, entry_date, entry_type, idempotency_key, status) "
            "VALUES ('p', '2026-01-01', 'STANDARD', 'kp', 'POSTED')"
        )


def test_zero_amount_line_is_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        make_entry(conn, amounts=(0, 0))


def test_line_cannot_be_inserted_into_posted_entry(conn):
    make_entry(conn)
    post(conn, "e1")
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABILITY_ERROR"):
        conn.execute(
            "INSERT INTO journal_lines (id, journal_entry_id, account_id, signed_amount_minor) "
            "VALUES ('x', 'e1', ?, 5)",
            (ACCOUNT_A,),
        )


def test_line_of_posted_entry_cannot_be_updated(conn):
    make_entry(conn)
    post(conn, "e1")
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABILITY_ERROR"):
        conn.execute("UPDATE journal_lines SET signed_amount_minor = 1 WHERE id = 'e1-l0'")


def test_line_of_posted_entry_cannot_be_deleted(conn):
    make_entry(conn)
    post(conn, "e1")
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABILITY_ERROR"):
        conn.execute("DELETE FROM journal_lines WHERE id = 'e1-l0'")


def test_draft_lines_remain_editable(conn):
    make_entry(conn, amounts=(100, -50))
    conn.execute("UPDATE journal_lines SET signed_amount_minor = -100 WHERE id = 'e1-l1'")
    post(conn, "e1")
    assert status(conn, "e1") == "POSTED"


def test_posted_committed_entry_cannot_be_deleted(conn):
    make_entry(conn)
    post(conn, "e1")
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABILITY_ERROR"):
        conn.execute("DELETE FROM journal_entries WHERE id = 'e1'")
    assert count(conn, "journal_lines") == 2


def test_provisional_draft_entry_delete_cascades_lines(conn):
    make_entry(conn, provisional=1)
    conn.execute("DELETE FROM journal_entries WHERE id = 'e1'")
    assert count(conn, "journal_lines") == 0


def test_provisional_posted_entry_delete_cascades_lines(conn):
    make_entry(conn, provisional=1)
    post(conn, "e1")
    conn.execute("DELETE FROM journal_entries WHERE id = 'e1'")
    assert count(conn, "journal_lines") == 0
    assert count(conn, "journal_entries") == 0


def test_posted_entry_cannot_return_to_draft(conn):
    make_entry(conn)
    post(conn, "e1")
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABILITY_ERROR"):
        conn.execute("UPDATE journal_entries SET status = 'DRAFT' WHERE id = 'e1'")


def test_foreign_keys_are_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO journal_lines (id, journal_entry_id, account_id, signed_amount_minor) "
            "VALUES ('orphan', 'missing', ?, 5)",
            (ACCOUNT_A,),
        )


def test_transaction_rolls_back_on_error(conn):
    with pytest.raises(RuntimeError), transaction(conn):
        make_entry(conn)
        raise RuntimeError("boom")
    assert count(conn, "journal_entries") == 0


def test_transaction_commits_on_success(conn):
    with transaction(conn):
        make_entry(conn)
    assert count(conn, "journal_entries") == 1


def test_connection_pragmas_are_applied(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2
