import sqlite3

import pytest

from app.database.migrate import MigrationError, apply_migrations
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


# --- posted-entry freezing, provisional upgrade, replace attack, currency, types -------------

INSERT_STATEMENT = (
    "INSERT INTO statements (id, account_id, statement_kind, original_filename, file_hash_sha256, "
    "layout_fingerprint, parser_name, parser_version, storage_path, statement_start_date, "
    "statement_end_date, opening_balance_minor, closing_balance_minor, processing_status) "
    "VALUES ('s1', ?, 'CSV', 'f.csv', 'h', 'fp', 'p', '1', '/x', '2026-01-01', '2026-01-31', 0, 0, "
    "'APPROVED')"
)


def make_posted(conn, entry_id="e1", provisional=0):
    make_entry(conn, entry_id, provisional=provisional)
    post(conn, entry_id)
    return entry_id


def test_posted_entry_cannot_become_provisional(conn):
    make_posted(conn)
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABILITY_ERROR"):
        conn.execute("UPDATE journal_entries SET is_provisional = 1 WHERE id = 'e1'")


def test_flip_to_provisional_then_delete_attack_is_refused(conn):
    make_posted(conn)
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABILITY_ERROR"):
        conn.execute("UPDATE journal_entries SET is_provisional = 1 WHERE id = 'e1'")
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABILITY_ERROR"):
        conn.execute("DELETE FROM journal_entries WHERE id = 'e1'")
    assert count(conn, "journal_lines") == 2


def test_provisional_posted_entry_can_be_upgraded_to_committed(conn):
    make_posted(conn, provisional=1)
    conn.execute("UPDATE journal_entries SET is_provisional = 0 WHERE id = 'e1'")
    flag = conn.execute("SELECT is_provisional FROM journal_entries WHERE id = 'e1'").fetchone()[0]
    assert flag == 0


def test_provisional_upgrade_can_set_source_statement(conn):
    make_posted(conn, provisional=1)
    conn.execute(INSERT_STATEMENT, (ACCOUNT_A,))
    conn.execute("UPDATE journal_entries SET is_provisional = 0, source_statement_id = 's1' WHERE id = 'e1'")
    row = conn.execute("SELECT is_provisional, source_statement_id FROM journal_entries").fetchone()
    assert tuple(row) == (0, "s1")


def test_committed_entry_source_statement_cannot_change(conn):
    make_posted(conn)
    conn.execute(INSERT_STATEMENT, (ACCOUNT_A,))
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABILITY_ERROR"):
        conn.execute("UPDATE journal_entries SET source_statement_id = 's1' WHERE id = 'e1'")


@pytest.mark.parametrize(
    "assignment",
    ["entry_date = '2030-01-01'", "entry_type = 'REFUND'", "idempotency_key = 'other'"],
)
def test_posted_entry_fields_cannot_be_updated(conn, assignment):
    make_posted(conn)
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABILITY_ERROR"):
        conn.execute(f"UPDATE journal_entries SET {assignment} WHERE id = 'e1'")


def test_posting_cannot_change_other_columns(conn):
    make_entry(conn)
    with pytest.raises(sqlite3.IntegrityError, match="LEDGER_INTEGRITY_ERROR"):
        conn.execute(
            "UPDATE journal_entries SET status = 'POSTED', entry_date = '2031-01-01' WHERE id = 'e1'"
        )
    assert status(conn, "e1") == "DRAFT"


def test_insert_or_replace_cannot_replace_posted_committed_entry(conn):
    make_posted(conn)
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABILITY_ERROR"):
        conn.execute(
            "INSERT OR REPLACE INTO journal_entries (id, entry_date, entry_type, idempotency_key) "
            "VALUES ('evil', '2026-01-01', 'STANDARD', 'key-e1')"
        )
    assert count(conn, "journal_lines") == 2
    assert status(conn, "e1") == "POSTED"


def test_recursive_triggers_pragma_is_on(conn):
    assert conn.execute("PRAGMA recursive_triggers").fetchone()[0] == 1


def test_mixed_currency_entry_refuses_to_post(conn):
    make_entry(conn)
    conn.execute("UPDATE journal_lines SET currency = 'USD' WHERE id = 'e1-l0'")
    with pytest.raises(sqlite3.IntegrityError, match="single currency"):
        post(conn, "e1")


@pytest.mark.parametrize("amount", [1.5, "abc", "1.5"])
def test_non_integer_line_amount_is_rejected(conn, amount):
    conn.execute(
        "INSERT INTO journal_entries (id, entry_date, entry_type, idempotency_key) "
        "VALUES ('t', '2026-01-01', 'STANDARD', 'kt')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO journal_lines (id, journal_entry_id, account_id, signed_amount_minor) "
            "VALUES ('tl', 't', ?, ?)",
            (ACCOUNT_A, amount),
        )


# --- migration runner -------------------------------------------------------------------------


def _migration_dir(tmp_path, files):
    d = tmp_path / "migs"
    d.mkdir()
    for name, body in files.items():
        (d / name).write_text(body, encoding="utf-8")
    return d


def test_failing_migration_rolls_back_and_records_nothing(tmp_path):
    c = connect(tmp_path / "m.db")
    d = _migration_dir(
        tmp_path,
        {"0001_bad.sql": "CREATE TABLE t1 (a INTEGER);\nINSERT INTO missing_table VALUES (1);\n"},
    )
    try:
        with pytest.raises(sqlite3.Error):
            apply_migrations(c, d)
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE name = 't1'")]
        recorded = c.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        assert tables == []
        assert recorded == 0
        assert not c.in_transaction
    finally:
        c.close()


@pytest.mark.parametrize("control", ["COMMIT;", "BEGIN;", "BEGIN IMMEDIATE;", "ROLLBACK;"])
def test_migration_with_transaction_control_is_rejected(tmp_path, control):
    c = connect(tmp_path / "m.db")
    d = _migration_dir(tmp_path, {"0001_x.sql": f"CREATE TABLE t1 (a INTEGER);\n{control}\n"})
    try:
        with pytest.raises(MigrationError, match="transaction-control"):
            apply_migrations(c, d)
        assert c.execute("SELECT COUNT(*) FROM sqlite_master WHERE name = 't1'").fetchone()[0] == 0
    finally:
        c.close()


def test_migration_with_trigger_body_is_accepted(tmp_path):
    c = connect(tmp_path / "m.db")
    body = "CREATE TABLE t1 (a INTEGER);\nCREATE TRIGGER tr BEFORE INSERT ON t1\nBEGIN\n    SELECT 1;\nEND;\n"
    d = _migration_dir(tmp_path, {"0001_trig.sql": body})
    try:
        assert apply_migrations(c, d) == ["0001_trig"]
    finally:
        c.close()


def test_migration_filenames_must_match_strict_pattern(tmp_path):
    c = connect(tmp_path / "m.db")
    d = _migration_dir(tmp_path, {"0001_Bad-Name.sql": "CREATE TABLE t1 (a INTEGER);"})
    try:
        assert apply_migrations(c, d) == []
    finally:
        c.close()


# --- transaction() ----------------------------------------------------------------------------


_INSERT_BUDGET = "INSERT INTO budgets (id, name, period_month, total_limit_minor) VALUES ('b1', 'B', '2026-01', 1)"


def test_nested_transaction_joins_outer_and_commits_once(conn):
    with transaction(conn):
        with transaction(conn):
            conn.execute(_INSERT_BUDGET)
        assert conn.in_transaction
    assert not conn.in_transaction
    assert conn.execute("SELECT COUNT(*) FROM budgets").fetchone()[0] == 1


def test_failure_in_nested_transaction_rolls_back_the_outer_work(conn):
    with pytest.raises(RuntimeError), transaction(conn):
        conn.execute(_INSERT_BUDGET)
        with transaction(conn):
            raise RuntimeError("boom")
    assert not conn.in_transaction
    assert conn.execute("SELECT COUNT(*) FROM budgets").fetchone()[0] == 0


def test_transaction_leaves_no_open_transaction_after_failure(conn):
    with pytest.raises(RuntimeError), transaction(conn):
        raise RuntimeError("boom")
    assert not conn.in_transaction
