from datetime import date

import pytest

from app.database import seed
from app.finance import chart
from app.finance.ledger_service import LedgerService
from app.ingestion.drift_guard import LayoutDriftError
from app.ingestion.pipeline import (
    DuplicateStatementError,
    InvalidRowUpdateError,
    RowNotFoundError,
    StatementRejectedError,
    get_review,
    get_statement_row,
    ingest_statement,
    update_row,
)
from tests.ingestion_fakes import (
    FakeParser,
    InMemoryDocumentStore,
    add_merchant,
    add_provisional,
    ingest,
    make_account,
    make_statement,
    upi,
    verify_layout,
)

D = date(2026, 3, 10)


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


def table_count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608


def rows_of(conn, statement_id):
    return get_review(conn, statement_id).rows


def test_happy_path_counts_and_staging(conn, account, store, food):
    parsed = make_statement(
        [
            (D, upi("111111111111", "SWIGGY", "swiggy@ybl"), 25_000, 0),
            (D, "ATM CASH WITHDRAWAL", 10_000, 0),
            (D, "SALARY ACME", 0, 500_000),
        ]
    )
    result = ingest(conn, account, parsed, store)
    assert (result.row_count, result.auto_approved_count, result.pending_review_count) == (3, 1, 2)
    assert (result.duplicate_count, result.mismatch_count, result.reconciliation_diff_minor) == (0, 0, 0)
    assert result.processing_status == "REVIEW_REQUIRED"
    first = rows_of(conn, result.statement_id)[0]
    assert (first["row_status"], first["suggested_category_id"], first["confidence_score"]) == (
        "AUTO_APPROVED", food, 0.99,
    )  # fmt: skip
    review = get_review(conn, result.statement_id)
    assert review.statement["computed_closing_minor"] == parsed.closing_balance_minor
    assert "storage_path" not in review.statement
    assert len(store.saved) == 1
    assert (
        conn.execute("SELECT COUNT(*) FROM audit_events WHERE event_type='STATEMENT_UPLOADED'").fetchone()[0]
        == 1
    )


@pytest.mark.parametrize(
    ("content", "code"),
    [(b"a" * (25 * 1024 * 1024 + 1), "FILE_TOO_LARGE"), (b"\xff\xfe\x00\x01", "UNSUPPORTED_FILE_TYPE")],
)
def test_file_rejections(conn, account, store, content, code):
    parsed = make_statement([(D, "X", 1, 0)])
    with pytest.raises(StatementRejectedError, match=code):
        ingest(conn, account, parsed, store, content=content)
    assert table_count(conn, "statements") == 0


def test_pdf_signature_is_accepted(conn, account, store):
    parsed = make_statement([(D, "X", 1, 0)])
    ingest(conn, account, parsed, store, content=b"%PDF-1.7\n\xff\xfe binary")
    assert table_count(conn, "statements") == 1


def test_unknown_and_inactive_accounts_are_rejected(conn, account, store):
    parsed = make_statement([(D, "X", 1, 0)])
    with pytest.raises(StatementRejectedError, match="ACCOUNT_NOT_FOUND"):
        ingest(conn, "missing", parsed, store)
    conn.execute("UPDATE accounts SET is_active = 0 WHERE id = ?", (account,))
    with pytest.raises(StatementRejectedError, match="ACCOUNT_INACTIVE"):
        ingest(conn, account, parsed, store)


def test_no_parser_is_rejected(conn, account, store):
    parsed = make_statement([(D, "X", 1, 0)])
    with pytest.raises(StatementRejectedError, match="NO_PARSER"):
        ingest_statement(
            conn, account_id=account, filename="a.csv", content=b"x", statement_kind="CSV",
            parsers=[FakeParser(parsed, accepts=False)], document_store=store,
            verify_layout=verify_layout,
        )  # fmt: skip


def test_duplicate_file_raises_with_existing_id(conn, account, store):
    parsed = make_statement([(D, "X", 1, 0)])
    first = ingest(conn, account, parsed, store, content=b"same-bytes")
    with pytest.raises(DuplicateStatementError) as err:
        ingest(conn, account, parsed, store, content=b"same-bytes")
    assert err.value.statement_id == first.statement_id
    assert table_count(conn, "statements") == 1


def test_layout_drift_halts_and_writes_nothing(conn, account, store):
    first = ingest(conn, account, make_statement([(D, "X", 1, 0)]), store)
    conn.execute("UPDATE statements SET processing_status='APPROVED', approved_at='2026-04-01'")
    drifted = make_statement([(D, "Y", 2, 0)], fingerprint="layout-b")
    with pytest.raises(LayoutDriftError):
        ingest(conn, account, drifted, store)
    assert table_count(conn, "statements") == 1
    assert table_count(conn, "statement_rows") == 1
    assert first.statement_id


def test_balance_mismatch_creates_import_error_and_forces_review(conn, account, store, food):
    parsed = make_statement(
        [
            (D, upi("111111111111", "SWIGGY", "swiggy@ybl"), 25_000, 0),
            (D, upi("222222222222", "SWIGGY", "swiggy@ybl"), 5_000, 0),
        ],
        stated_overrides={2: 69_000},
    )
    result = ingest(conn, account, parsed, store)
    assert result.mismatch_count == 1
    assert result.auto_approved_count == 0
    assert result.pending_review_count == 2
    errors = get_review(conn, result.statement_id).import_errors
    assert len(errors) == 1
    assert errors[0]["error_code"] == "RUNNING_BALANCE_MISMATCH"
    assert (errors[0]["expected_running_balance_minor"], errors[0]["actual_running_balance_minor"]) == (
        70_000, 69_000,
    )  # fmt: skip


def test_closing_balance_difference_blocks_auto_approval(conn, account, store, food):
    parsed = make_statement([(D, upi("111111111111", "SWIGGY", "swiggy@ybl"), 25_000, 0)], closing=1)
    result = ingest(conn, account, parsed, store)
    assert result.reconciliation_diff_minor == 74_999
    assert result.auto_approved_count == 0


def test_rows_matching_existing_transactions_are_duplicates(conn, account, store, food):
    ledger = LedgerService(conn)
    by_ref = ledger.record_expense(
        source_account_id=account, category_id=food, amount_minor=25_000, tx_date=D,
        idempotency_key="k1", external_reference="111111111111",
    )  # fmt: skip
    first = make_statement([(D, "COFFEE SHOP", 3_000, 0)])
    fingerprint = ingest(conn, account, first, InMemoryDocumentStore()).statement_id
    fp = rows_of(conn, fingerprint)[0]["dedup_fingerprint"]
    by_fp = ledger.record_expense(
        source_account_id=account, category_id=food, amount_minor=3_000, tx_date=D,
        idempotency_key="k2", dedup_fingerprint=fp,
    )  # fmt: skip
    parsed = make_statement(
        [
            (D, upi("111111111111", "SWIGGY", "swiggy@ybl"), 25_000, 0),
            (D, "COFFEE SHOP", 3_000, 0),
            (D, "OTHER", 1_000, 0),
        ]
    )
    result = ingest(conn, account, parsed, store)
    rows = rows_of(conn, result.statement_id)
    assert result.duplicate_count == 2
    assert [r["duplicate_of_transaction_id"] for r in rows] == [by_ref, by_fp, None]
    assert rows[0]["row_status"] == "DUPLICATE"


def test_superseded_transactions_do_not_count_as_duplicates(conn, account, store, food):
    ledger = LedgerService(conn)
    tx = ledger.record_expense(
        source_account_id=account, category_id=food, amount_minor=25_000, tx_date=D,
        idempotency_key="k1", external_reference="111111111111",
    )  # fmt: skip
    entry = conn.execute("SELECT journal_entry_id FROM transactions WHERE id=?", (tx,)).fetchone()[0]
    ledger.reverse_entry(journal_entry_id=entry, entry_date=D, idempotency_key="rev")
    parsed = make_statement([(D, upi("111111111111", "SWIGGY", "swiggy@ybl"), 25_000, 0)])
    assert ingest(conn, account, parsed, store).duplicate_count == 0


@pytest.mark.parametrize(("offset", "matches"), [(3, True), (-3, True), (4, False), (-4, False)])
def test_provisional_window_boundary(conn, account, store, food, offset, matches):
    prov = add_provisional(conn, account, food, 4_000, date(2026, 3, 10 + offset), key="p1")
    result = ingest(conn, account, make_statement([(D, "SHOP", 4_000, 0)]), store)
    row = rows_of(conn, result.statement_id)[0]
    assert row["provisional_match_transaction_id"] == (prov if matches else None)


def test_provisional_matches_by_external_reference_outside_window(conn, account, store, food):
    prov = add_provisional(
        conn, account, food, 25_000, date(2026, 3, 1), key="p1", external_reference="111111111111"
    )
    parsed = make_statement([(D, upi("111111111111", "SWIGGY", "swiggy@ybl"), 25_000, 0)])
    row = rows_of(conn, ingest(conn, account, parsed, store).statement_id)[0]
    assert row["provisional_match_transaction_id"] == prov


def test_provisional_is_claimed_once_and_closest_date_wins(conn, account, store, food):
    far = add_provisional(conn, account, food, 4_000, date(2026, 3, 12), key="far")
    near = add_provisional(conn, account, food, 4_000, date(2026, 3, 11), key="near")
    result = ingest(
        conn, account, make_statement([(D, "A", 4_000, 0), (D, "B", 4_000, 0), (D, "C", 4_000, 0)]), store
    )
    matches = [r["provisional_match_transaction_id"] for r in rows_of(conn, result.statement_id)]
    assert matches == [near, far, None]


def test_update_row_transitions(conn, account, store, food):
    parsed = make_statement(
        [(D, "ATM", 1_000, 0), (D, upi("111111111111", "SWIGGY", "swiggy@ybl"), 2_000, 0)]
    )
    result = ingest(conn, account, parsed, store)
    pending, auto = rows_of(conn, result.statement_id)
    update_row(conn, pending["id"], row_status="USER_APPROVED", suggested_category_id=food)
    update_row(conn, auto["id"], row_status="REJECTED")
    update_row(conn, auto["id"], row_status="PENDING_REVIEW")
    rows = rows_of(conn, result.statement_id)
    assert (rows[0]["row_status"], rows[0]["suggested_category_id"]) == ("USER_APPROVED", food)
    assert rows[1]["row_status"] == "PENDING_REVIEW"


def test_update_row_rejects_invalid_changes(conn, account, store, food):
    income = chart.create_category(conn, name="Pay", category_type="INCOME")[0]
    result = ingest(conn, account, make_statement([(D, "ATM", 1_000, 0)]), store)
    row_id = rows_of(conn, result.statement_id)[0]["id"]
    with pytest.raises(InvalidRowUpdateError):
        update_row(conn, row_id, row_status="COMMITTED")
    with pytest.raises(InvalidRowUpdateError):
        update_row(conn, row_id, row_status="AUTO_APPROVED")
    with pytest.raises(InvalidRowUpdateError):
        update_row(conn, row_id, suggested_category_id=income)
    with pytest.raises(InvalidRowUpdateError):
        update_row(conn, row_id)
    conn.execute("UPDATE statements SET processing_status = 'APPROVED'")
    with pytest.raises(InvalidRowUpdateError):
        update_row(conn, row_id, row_status="USER_APPROVED")


def _duplicate_row(conn, account, store, food, amount=25_000):
    LedgerService(conn).record_expense(
        source_account_id=account,
        category_id=food,
        amount_minor=25_000,
        tx_date=D,
        idempotency_key="k1",
        external_reference="111111111111",
    )
    parsed = make_statement([(D, upi("111111111111", "SWIGGY", "swiggy@ybl"), amount, 0)])
    return rows_of(conn, ingest(conn, account, parsed, store).statement_id)[0]


def test_get_statement_row_matches_review_row_shape(conn, account, store):
    result = ingest(conn, account, make_statement([(D, "ATM", 1_000, 0)]), store)
    review_row = rows_of(conn, result.statement_id)[0]
    update_row(conn, review_row["id"], row_status="USER_APPROVED")
    row = get_statement_row(conn, review_row["id"])
    assert row == {**review_row, "row_status": "USER_APPROVED"}


def test_get_statement_row_unknown_id_raises(conn):
    with pytest.raises(RowNotFoundError):
        get_statement_row(conn, "missing")


def test_duplicate_row_can_be_overridden_but_not_rejected(conn, account, store, food):
    row = _duplicate_row(conn, account, store, food)
    assert row["row_status"] == "DUPLICATE"
    with pytest.raises(InvalidRowUpdateError):
        update_row(conn, row["id"], row_status="REJECTED")
    with pytest.raises(InvalidRowUpdateError):
        update_row(conn, row["id"], suggested_category_id=food)
    update_row(conn, row["id"], row_status="USER_APPROVED")
    again = conn.execute("SELECT * FROM statement_rows WHERE id = ?", (row["id"],)).fetchone()
    assert (again["row_status"], again["duplicate_override"]) == ("USER_APPROVED", 1)


def test_committed_rows_are_immutable(conn, account, store):
    result = ingest(conn, account, make_statement([(D, "ATM", 1_000, 0)]), store)
    row_id = rows_of(conn, result.statement_id)[0]["id"]
    conn.execute("UPDATE statement_rows SET row_status = 'COMMITTED' WHERE id = ?", (row_id,))
    with pytest.raises(InvalidRowUpdateError):
        update_row(conn, row_id, row_status="PENDING_REVIEW")


def test_reference_match_with_different_amount_is_not_a_duplicate(conn, account, store, food):
    row = _duplicate_row(conn, account, store, food, amount=26_000)
    assert row["row_status"] != "DUPLICATE"
    assert row["duplicate_of_transaction_id"] is None


def test_merchants_are_loaded_once_per_ingest(conn, account, store, food):
    queries: list[str] = []
    conn.set_trace_callback(lambda sql: queries.append(sql) if "FROM merchants" in sql else None)
    parsed = make_statement([(D, "A", 1_000, 0), (D, "B", 1_000, 0), (D, "C", 1_000, 0)])
    ingest(conn, account, parsed, store)
    conn.set_trace_callback(None)
    assert len(queries) == 1


def test_document_store_failure_leaves_no_rows(conn, account):
    class Failing:
        def save(self, content, sha256_hex):
            raise OSError("disk full")

    with pytest.raises(OSError, match="disk full"):
        ingest(conn, account, make_statement([(D, "X", 1, 0)]), Failing())  # type: ignore[arg-type]
    assert table_count(conn, "statements") == 0
    assert table_count(conn, "statement_rows") == 0


def test_uncategorized_fallback_ids_exist(conn):
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM categories WHERE id IN (?, ?)",
            (seed.UNCATEGORIZED_EXPENSE_CATEGORY_ID, seed.UNCATEGORIZED_INCOME_CATEGORY_ID),
        ).fetchone()[0]
        == 2
    )
