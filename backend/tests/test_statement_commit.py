from datetime import date

import pytest

from app.finance import chart
from app.finance.ledger_service import LedgerService, SplitShareSpec
from app.ingestion.pipeline import DuplicateStatementError, get_review, update_row
from app.ingestion.statement_commit import StatementNotReconciledError, commit_statement
from tests.ingestion_fakes import (
    InMemoryDocumentStore,
    add_merchant,
    ingest,
    make_account,
    make_statement,
    upi,
)

D = date(2026, 3, 10)
SWIGGY = upi("111111111111", "SWIGGY", "swiggy@ybl")


@pytest.fixture
def account(conn):
    return make_account(conn)


@pytest.fixture
def store():
    return InMemoryDocumentStore()


@pytest.fixture
def food(conn):
    category_id = chart.create_category(conn, name="Food", category_type="EXPENSE")[0]
    add_merchant(conn, "Swiggy", category_id, vpas=["swiggy@ybl"])
    return category_id


def approve_pending(conn, statement_id):
    for row in get_review(conn, statement_id).rows:
        if row["row_status"] == "PENDING_REVIEW":
            update_row(conn, row["id"], row_status="USER_APPROVED")


def staged(conn, account, store, rows, **kwargs):
    parsed = make_statement(rows, **kwargs)
    return ingest(conn, account, parsed, store), parsed


def journal_count(conn):
    return conn.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0]


def test_commit_happy_path(conn, account, store, food):
    result, parsed = staged(
        conn, account, store, [(D, SWIGGY, 25_000, 0), (D, "ATM CASH", 10_000, 0), (D, "SALARY", 0, 500_000)]
    )
    approve_pending(conn, result.statement_id)
    out = commit_statement(conn, result.statement_id, idempotency_key="k")
    assert (out.committed_count, out.skipped_count, out.already_committed) == (3, 0, False)
    ledger = LedgerService(conn)
    assert ledger.verify_integrity().is_clean
    assert ledger.account_balance(account) == parsed.closing_balance_minor
    review = get_review(conn, result.statement_id)
    assert review.statement["processing_status"] == "APPROVED"
    assert review.statement["approved_at"]
    assert all(r["row_status"] == "COMMITTED" and r["committed_transaction_id"] for r in review.rows)
    statuses = [
        conn.execute(
            "SELECT review_status FROM transactions WHERE id=?", (r["committed_transaction_id"],)
        ).fetchone()[0]
        for r in review.rows
    ]
    assert statuses == ["AUTO_APPROVED", "USER_APPROVED", "USER_APPROVED"]
    snap = conn.execute("SELECT * FROM account_balance_snapshots WHERE account_id=?", (account,)).fetchone()
    assert (snap["snapshot_date"], snap["balance_minor"], snap["source"]) == (
        "2026-03-31", parsed.closing_balance_minor, "STATEMENT_RECONCILED",
    )  # fmt: skip
    audit = "SELECT COUNT(*) FROM audit_events WHERE event_type='STATEMENT_COMMITTED'"
    assert conn.execute(audit).fetchone()[0] == 1
    tx = conn.execute(
        "SELECT * FROM transactions WHERE statement_id=? AND merchant_id IS NOT NULL", (result.statement_id,)
    ).fetchone()
    assert tx["merchant_id"] is not None


def test_rejected_and_duplicate_rows_are_skipped(conn, account, store, food):
    result, parsed = staged(conn, account, store, [(D, "ATM", 1_000, 0), (D, "FEE", 500, 0)])
    rows = get_review(conn, result.statement_id).rows
    update_row(conn, rows[0]["id"], row_status="USER_APPROVED")
    update_row(conn, rows[1]["id"], row_status="REJECTED")
    out = commit_statement(conn, result.statement_id, idempotency_key="k")
    assert (out.committed_count, out.skipped_count) == (1, 1)
    # A rejected row leaves the ledger short of the statement closing balance by design.
    assert LedgerService(conn).account_balance(account) == parsed.closing_balance_minor + 500


def test_commit_refused_while_rows_pending(conn, account, store):
    result, _ = staged(conn, account, store, [(D, "ATM", 1_000, 0)])
    with pytest.raises(StatementNotReconciledError):
        commit_statement(conn, result.statement_id, idempotency_key="k")
    assert journal_count(conn) == 0


def test_commit_refused_when_unreconciled(conn, account, store):
    result, _ = staged(conn, account, store, [(D, "ATM", 1_000, 0)], closing=5)
    approve_pending(conn, result.statement_id)
    with pytest.raises(StatementNotReconciledError):
        commit_statement(conn, result.statement_id, idempotency_key="k")
    assert journal_count(conn) == 0


def test_commit_refused_with_import_errors(conn, account, store):
    result, _ = staged(
        conn, account, store, [(D, "ATM", 1_000, 0)], stated_overrides={1: 99_001}, closing=99_001
    )
    assert result.mismatch_count == 1
    approve_pending(conn, result.statement_id)
    with pytest.raises(StatementNotReconciledError):
        commit_statement(conn, result.statement_id, idempotency_key="k")


def test_commit_replay_is_a_noop(conn, account, store):
    result, _ = staged(conn, account, store, [(D, "ATM", 1_000, 0)])
    approve_pending(conn, result.statement_id)
    commit_statement(conn, result.statement_id, idempotency_key="k")
    before = journal_count(conn)
    again = commit_statement(conn, result.statement_id, idempotency_key="k")
    assert (again.already_committed, again.committed_count) == (True, 0)
    assert journal_count(conn) == before


def test_unknown_statement_and_blank_key(conn):
    with pytest.raises(ValueError, match="Unknown"):
        commit_statement(conn, "nope", idempotency_key="k")
    with pytest.raises(ValueError, match="idempotency_key"):
        commit_statement(conn, "nope", idempotency_key="")


def test_failure_midway_rolls_everything_back(conn, account, store, monkeypatch):
    result, _ = staged(conn, account, store, [(D, "ATM", 1_000, 0), (D, "SALARY", 0, 9_000)])
    approve_pending(conn, result.statement_id)

    def boom(self, **kwargs):
        raise RuntimeError("injected")

    monkeypatch.setattr(LedgerService, "record_income", boom)
    with pytest.raises(RuntimeError, match="injected"):
        commit_statement(conn, result.statement_id, idempotency_key="k")
    assert not conn.in_transaction
    assert journal_count(conn) == 0
    review = get_review(conn, result.statement_id)
    assert review.statement["processing_status"] == "REVIEW_REQUIRED"
    assert all(r["row_status"] == "USER_APPROVED" for r in review.rows)
    assert conn.execute("SELECT COUNT(*) FROM account_balance_snapshots").fetchone()[0] == 0
    assert LedgerService(conn).account_balance(account) == 0
    monkeypatch.undo()
    assert commit_statement(conn, result.statement_id, idempotency_key="k").committed_count == 2


def test_provisional_upgrade_keeps_notes_and_splits(conn, account, store, food):
    ledger = LedgerService(conn)
    prov = ledger.record_expense(
        source_account_id=account, category_id=food, amount_minor=4_000, tx_date=date(2026, 3, 11),
        idempotency_key="quick", is_provisional=True,
        splits=[SplitShareSpec("Friend", None, 1_000)],
    )  # fmt: skip
    conn.execute("UPDATE transactions SET notes = 'dinner' WHERE id = ?", (prov,))
    result, parsed = staged(conn, account, store, [(D, "RESTAURANT BILL", 4_000, 0)])
    assert get_review(conn, result.statement_id).rows[0]["provisional_match_transaction_id"] == prov
    approve_pending(conn, result.statement_id)
    commit_statement(conn, result.statement_id, idempotency_key="k")

    tx = conn.execute("SELECT * FROM transactions WHERE id = ?", (prov,)).fetchone()
    assert (tx["statement_id"], tx["review_status"], tx["notes"], tx["version"]) == (
        result.statement_id, "USER_APPROVED", "dinner", 2,
    )  # fmt: skip
    assert tx["description"] == "RESTAURANT BILL"
    entry = conn.execute("SELECT * FROM journal_entries WHERE id = ?", (tx["journal_entry_id"],)).fetchone()
    assert (entry["is_provisional"], entry["source_statement_id"]) == (0, result.statement_id)
    assert (
        conn.execute("SELECT COUNT(*) FROM reimbursable_splits WHERE transaction_id=?", (prov,)).fetchone()[0]
        == 1
    )
    expenses = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE account_id=? AND transaction_type='EXPENSE'", (account,)
    ).fetchone()[0]
    assert expenses == 1
    assert get_review(conn, result.statement_id).rows[0]["committed_transaction_id"] == prov
    assert ledger.verify_integrity().is_clean
    assert ledger.account_balance(account) == parsed.closing_balance_minor


def test_reingesting_same_file_after_commit_is_duplicate(conn, account, store):
    parsed = make_statement([(D, "ATM", 1_000, 0)])
    result = ingest(conn, account, parsed, store, content=b"fixed")
    approve_pending(conn, result.statement_id)
    commit_statement(conn, result.statement_id, idempotency_key="k")
    with pytest.raises(DuplicateStatementError):
        ingest(conn, account, parsed, store, content=b"fixed")


def test_second_statement_does_not_repost_opening_balance(conn, account, store):
    first, _ = staged(conn, account, store, [(D, "ATM", 1_000, 0)])
    approve_pending(conn, first.statement_id)
    commit_statement(conn, first.statement_id, idempotency_key="k1")
    second, parsed = staged(
        conn, account, store, [(date(2026, 4, 5), "FEE", 100, 0)], opening=99_000,
        start=date(2026, 4, 1), end=date(2026, 4, 30),
    )  # fmt: skip
    approve_pending(conn, second.statement_id)
    commit_statement(conn, second.statement_id, idempotency_key="k2")
    ledger = LedgerService(conn)
    assert ledger.account_balance(account) == parsed.closing_balance_minor
    assert ledger.verify_integrity().is_clean


def _two_overlapping(conn, account, store):
    rows = [
        (D, upi("111111111111", "SWIGGY", "swiggy@ybl"), 25_000, 0),
        (D, upi("222222222222", "SHOP", "shop@ybl"), 5_000, 0),
    ]
    first, parsed = staged(conn, account, store, rows)
    second, _ = staged(conn, account, store, rows)
    for sid in (first.statement_id, second.statement_id):
        approve_pending(conn, sid)
    return first, second, parsed


def test_overlapping_statements_do_not_double_post(conn, account, store, food):
    first, second, parsed = _two_overlapping(conn, account, store)
    commit_statement(conn, first.statement_id, idempotency_key="k1")
    before = journal_count(conn)
    out = commit_statement(conn, second.statement_id, idempotency_key="k2")
    assert (out.committed_count, out.skipped_count, out.already_committed) == (0, 2, False)
    assert journal_count(conn) == before
    ledger = LedgerService(conn)
    assert ledger.account_balance(account) == parsed.closing_balance_minor
    assert ledger.verify_integrity().is_clean
    review = get_review(conn, second.statement_id)
    assert [r["row_status"] for r in review.rows] == ["DUPLICATE", "DUPLICATE"]
    assert all(r["duplicate_of_transaction_id"] for r in review.rows)
    assert review.statement["processing_status"] == "APPROVED"


def test_snapshot_written_when_everything_posts(conn, account, store):
    result, parsed = staged(conn, account, store, [(D, "ATM", 1_000, 0)])
    approve_pending(conn, result.statement_id)
    assert commit_statement(conn, result.statement_id, idempotency_key="k").snapshot_written is True
    row = conn.execute("SELECT balance_minor FROM account_balance_snapshots").fetchone()
    assert row["balance_minor"] == parsed.closing_balance_minor


def test_snapshot_skipped_when_a_row_was_rejected(conn, account, store):
    result, _ = staged(conn, account, store, [(D, "ATM", 1_000, 0), (D, "FEE", 500, 0)])
    rows = get_review(conn, result.statement_id).rows
    update_row(conn, rows[0]["id"], row_status="USER_APPROVED")
    update_row(conn, rows[1]["id"], row_status="REJECTED")
    out = commit_statement(conn, result.statement_id, idempotency_key="k")
    assert out.snapshot_written is False
    assert conn.execute("SELECT COUNT(*) FROM account_balance_snapshots").fetchone()[0] == 0


def test_overridden_duplicate_survives_the_commit_recheck(conn, account, store, food):
    LedgerService(conn).record_expense(
        source_account_id=account,
        category_id=food,
        amount_minor=25_000,
        tx_date=D,
        idempotency_key="manual",
        external_reference="111111111111",
    )
    result, _ = staged(conn, account, store, [(D, upi("111111111111", "SWIGGY", "swiggy@ybl"), 25_000, 0)])
    row = get_review(conn, result.statement_id).rows[0]
    assert row["row_status"] == "DUPLICATE"
    update_row(conn, row["id"], row_status="USER_APPROVED")
    out = commit_statement(conn, result.statement_id, idempotency_key="k")
    assert (out.committed_count, out.skipped_count) == (1, 0)
    final = get_review(conn, result.statement_id).rows[0]
    assert (final["row_status"], final["duplicate_override"]) == ("COMMITTED", 1)
    sql = "SELECT COUNT(*) FROM transactions WHERE external_reference = '111111111111'"
    assert conn.execute(sql).fetchone()[0] == 2
    assert LedgerService(conn).verify_integrity().is_clean
