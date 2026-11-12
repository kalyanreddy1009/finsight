import sqlite3
from dataclasses import dataclass
from datetime import date

import pytest

from app.database import seed
from app.database.session import transaction
from app.finance import chart
from app.finance.ledger_service import (
    MAX_AMOUNT_MINOR,
    IdempotencyConflictError,
    LedgerService,
    SplitShareSpec,
)

DAY = date(2026, 11, 12)
TABLES = ("journal_entries", "journal_lines", "transactions", "reimbursable_splits")


@dataclass(frozen=True)
class World:
    svc: LedgerService
    conn: sqlite3.Connection
    bank_a: str
    bank_b: str
    card: str
    dining: str
    dining_ledger: str
    salary: str
    salary_ledger: str


@pytest.fixture
def world(conn: sqlite3.Connection) -> World:
    bank_a = chart.create_account(conn, name="Bank A", account_class="ASSET", account_subtype="BANK_SAVINGS")
    bank_b = chart.create_account(conn, name="Bank B", account_class="ASSET", account_subtype="BANK_CURRENT")
    card = chart.create_account(
        conn, name="Card", account_class="LIABILITY", account_subtype="CREDIT_CARD", credit_limit_minor=10**7
    )
    dining, dining_ledger = chart.create_category(conn, name="Dining", category_type="EXPENSE")
    salary, salary_ledger = chart.create_category(conn, name="Salary", category_type="INCOME")
    return World(
        LedgerService(conn), conn, bank_a, bank_b, card, dining, dining_ledger, salary, salary_ledger
    )


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}  # noqa: S608


def line_map(conn: sqlite3.Connection, tx_id: str) -> dict[str, int]:
    rows = conn.execute(
        "SELECT l.account_id, l.signed_amount_minor FROM journal_lines l "
        "JOIN transactions t ON t.journal_entry_id = l.journal_entry_id WHERE t.id = ?",
        (tx_id,),
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def entry_id(conn: sqlite3.Connection, tx_id: str) -> str:
    return conn.execute("SELECT journal_entry_id FROM transactions WHERE id = ?", (tx_id,)).fetchone()[0]


def class_total(conn: sqlite3.Connection, account_class: str) -> int:
    return conn.execute(
        "SELECT COALESCE(SUM(current_balance_minor), 0) FROM accounts WHERE account_class = ?",
        (account_class,),
    ).fetchone()[0]


def expense(w: World, key: str, amount: int = 50000, account: str | None = None, **kw) -> str:
    return w.svc.record_expense(
        source_account_id=account or w.bank_a,
        category_id=w.dining,
        amount_minor=amount,
        tx_date=DAY,
        idempotency_key=key,
        **kw,
    )


def split_expense(w: World, key: str = "split") -> tuple[str, list[str]]:
    specs = [SplitShareSpec("Asha", "asha@upi", 40000), SplitShareSpec("Ravi", None, 40000)]
    tx = expense(w, key, 120000, splits=specs)
    ids = [r[0] for r in w.conn.execute("SELECT id FROM reimbursable_splits ORDER BY counterparty_name")]
    return tx, ids


def settle(w: World, split_id: str, amount: int, key: str) -> str:
    return w.svc.settle_split(
        split_id=split_id, bank_account_id=w.bank_a, amount_minor=amount, tx_date=DAY, idempotency_key=key
    )


# ------------------------------------------------------------- posting matrix


def test_standard_bank_expense(world: World) -> None:
    tx = expense(world, "e1", 50000)
    assert line_map(world.conn, tx) == {world.bank_a: -50000, world.dining_ledger: 50000}
    assert world.svc.account_balance(world.bank_a) == -50000
    assert class_total(world.conn, "EXPENSE") == 50000
    assert world.svc.verify_integrity().is_clean


def test_credit_card_purchase(world: World) -> None:
    tx = expense(world, "e1", 200000, account=world.card)
    assert line_map(world.conn, tx) == {world.card: -200000, world.dining_ledger: 200000}
    assert world.svc.account_balance(world.card) == -200000
    assert class_total(world.conn, "EXPENSE") == 200000


def test_card_bill_payment_leaves_expense_unchanged(world: World) -> None:
    expense(world, "e1", 200000, account=world.card)
    tx = world.svc.record_transfer(
        from_account_id=world.bank_a, to_account_id=world.card, amount_minor=200000, tx_date=DAY,
        idempotency_key="pay",
    )  # fmt: skip
    assert line_map(world.conn, tx) == {world.card: 200000, world.bank_a: -200000}
    assert world.svc.account_balance(world.card) == 0
    assert class_total(world.conn, "EXPENSE") == 200000
    assert class_total(world.conn, "INCOME") == 0
    row = world.conn.execute(
        "SELECT t.transaction_type, e.entry_type FROM transactions t "
        "JOIN journal_entries e ON e.id = t.journal_entry_id WHERE t.id = ?",
        (tx,),
    ).fetchone()
    assert tuple(row) == ("CARD_SETTLEMENT", "CARD_SETTLEMENT")


def test_own_account_transfer(world: World) -> None:
    tx = world.svc.record_transfer(
        from_account_id=world.bank_a, to_account_id=world.bank_b, amount_minor=1000000, tx_date=DAY,
        idempotency_key="t1",
    )  # fmt: skip
    assert line_map(world.conn, tx) == {world.bank_b: 1000000, world.bank_a: -1000000}
    assert class_total(world.conn, "EXPENSE") == 0
    assert class_total(world.conn, "INCOME") == 0
    row = world.conn.execute(
        "SELECT t.transaction_type, e.entry_type FROM transactions t "
        "JOIN journal_entries e ON e.id = t.journal_entry_id WHERE t.id = ?",
        (tx,),
    ).fetchone()
    assert tuple(row) == ("TRANSFER", "INTERNAL_TRANSFER")


def test_merchant_refund_offsets_expense(world: World) -> None:
    original = expense(world, "e1", 50000)
    tx = world.svc.record_refund(
        dest_account_id=world.bank_a, original_transaction_id=original, amount_minor=50000,
        tx_date=DAY, idempotency_key="r1",
    )  # fmt: skip
    assert line_map(world.conn, tx) == {world.bank_a: 50000, world.dining_ledger: -50000}
    assert class_total(world.conn, "EXPENSE") == 0
    linked = world.conn.execute(
        "SELECT linked_transaction_id FROM transactions WHERE id = ?", (tx,)
    ).fetchone()
    assert linked[0] == original


def test_refund_to_card_reduces_liability(world: World) -> None:
    original = expense(world, "e1", 30000, account=world.card)
    world.svc.record_refund(
        dest_account_id=world.card, original_transaction_id=original, amount_minor=10000,
        tx_date=DAY, idempotency_key="r1",
    )  # fmt: skip
    assert world.svc.account_balance(world.card) == -20000
    assert class_total(world.conn, "EXPENSE") == 20000


def test_group_split_three_ways(world: World) -> None:
    tx, split_ids = split_expense(world)
    assert line_map(world.conn, tx) == {
        world.bank_a: -120000,
        world.dining_ledger: 40000,
        seed.PENDING_REIMBURSEMENTS_ACCOUNT_ID: 80000,
    }
    assert class_total(world.conn, "EXPENSE") == 40000
    row = world.conn.execute(
        "SELECT amount_minor, user_share_minor FROM transactions WHERE id = ?", (tx,)
    ).fetchone()
    assert tuple(row) == (120000, 40000)
    assert len(split_ids) == 2
    entry_type = world.conn.execute(
        "SELECT entry_type FROM journal_entries WHERE id = ?", (entry_id(world.conn, tx),)
    ).fetchone()[0]
    assert entry_type == "SPLIT_EXPENSE"
    statuses = {r[0] for r in world.conn.execute("SELECT status FROM reimbursable_splits")}
    assert statuses == {"OPEN"}


def test_friend_repayment_settles_receivable(world: World) -> None:
    _, split_ids = split_expense(world)
    tx = settle(world, split_ids[0], 40000, "s1")
    assert line_map(world.conn, tx) == {world.bank_a: 40000, seed.PENDING_REIMBURSEMENTS_ACCOUNT_ID: -40000}
    assert class_total(world.conn, "EXPENSE") == 40000
    assert class_total(world.conn, "INCOME") == 0
    assert world.svc.account_balance(seed.PENDING_REIMBURSEMENTS_ACCOUNT_ID) == 40000
    entry_type = world.conn.execute(
        "SELECT entry_type FROM journal_entries WHERE id = ?", (entry_id(world.conn, tx),)
    ).fetchone()[0]
    assert entry_type == "REIMBURSEMENT_SETTLEMENT"


def test_income_credits_income_account(world: World) -> None:
    tx = world.svc.record_income(
        dest_account_id=world.bank_a, category_id=world.salary, amount_minor=900000, tx_date=DAY,
        idempotency_key="i1",
    )  # fmt: skip
    assert line_map(world.conn, tx) == {world.bank_a: 900000, world.salary_ledger: -900000}
    assert class_total(world.conn, "INCOME") == -900000


def test_opening_balances_signed(world: World) -> None:
    world.svc.record_opening_balance(
        account_id=world.bank_a, amount_minor=500000, entry_date=DAY, idempotency_key="o1"
    )
    world.svc.record_opening_balance(
        account_id=world.card, amount_minor=-120000, entry_date=DAY, idempotency_key="o2"
    )
    assert world.svc.account_balance(world.bank_a) == 500000
    assert world.svc.account_balance(world.card) == -120000
    assert world.svc.account_balance(seed.OPENING_EQUITY_ACCOUNT_ID) == -380000
    assert world.svc.verify_integrity().is_clean


def test_split_equal_to_total_has_no_expense_line(world: World) -> None:
    tx = expense(world, "e1", 1000, splits=[SplitShareSpec("Asha", None, 1000)])
    assert line_map(world.conn, tx) == {world.bank_a: -1000, seed.PENDING_REIMBURSEMENTS_ACCOUNT_ID: 1000}
    user_share = world.conn.execute(
        "SELECT user_share_minor FROM transactions WHERE id = ?", (tx,)
    ).fetchone()
    assert user_share[0] == 0


def test_provisional_flags(world: World) -> None:
    tx = expense(world, "e1", is_provisional=True)
    status = world.conn.execute("SELECT review_status FROM transactions WHERE id = ?", (tx,)).fetchone()[0]
    flag = world.conn.execute(
        "SELECT is_provisional FROM journal_entries WHERE id = ?", (entry_id(world.conn, tx),)
    ).fetchone()[0]
    assert (status, flag) == ("PROVISIONAL", 1)
    normal = expense(world, "e2")
    assert (
        world.conn.execute("SELECT review_status FROM transactions WHERE id = ?", (normal,)).fetchone()[0]
        == "USER_APPROVED"
    )


# ----------------------------------------------------------------- idempotency


def test_idempotent_replay_of_every_method(world: World) -> None:
    w = world
    base = expense(w, "base", 100000)
    _, split_ids = split_expense(w, "base-split")
    calls = {
        "opening": lambda: w.svc.record_opening_balance(
            account_id=w.bank_b, amount_minor=777, entry_date=DAY, idempotency_key="k-open"
        ),
        "expense": lambda: expense(w, "k-exp", 4000),
        "expense_split": lambda: expense(w, "k-exp-split", 4000, splits=[SplitShareSpec("A", None, 1000)]),
        "income": lambda: w.svc.record_income(
            dest_account_id=w.bank_a, category_id=w.salary, amount_minor=5000, tx_date=DAY,
            idempotency_key="k-inc",
        ),
        "transfer": lambda: w.svc.record_transfer(
            from_account_id=w.bank_a, to_account_id=w.bank_b, amount_minor=300, tx_date=DAY,
            idempotency_key="k-tr",
        ),
        "refund": lambda: w.svc.record_refund(
            dest_account_id=w.bank_a, original_transaction_id=base, amount_minor=100000,
            tx_date=DAY, idempotency_key="k-ref",
        ),
        "settle": lambda: settle(w, split_ids[0], 40000, "k-set"),
        "reverse": lambda: w.svc.reverse_entry(
            journal_entry_id=entry_id(w.conn, expense(w, "k-to-reverse", 10)), entry_date=DAY,
            idempotency_key="k-rev",
        ),
    }  # fmt: skip
    for name, call in calls.items():
        first = call()
        before = counts(w.conn)
        balances = [
            tuple(r) for r in w.conn.execute("SELECT id, current_balance_minor FROM accounts ORDER BY id")
        ]
        assert call() == first, name
        assert counts(w.conn) == before, name
        after = [
            tuple(r) for r in w.conn.execute("SELECT id, current_balance_minor FROM accounts ORDER BY id")
        ]
        assert after == balances, name
    assert w.svc.verify_integrity().is_clean


# ------------------------------------------------------------------ validation


@pytest.mark.parametrize("bad", [1.5, 100.0, True, "100", None])
def test_non_int_amounts_raise_type_error(world: World, bad: object) -> None:
    with pytest.raises(TypeError):
        expense(world, "e", bad)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        world.svc.record_opening_balance(
            account_id=world.bank_a,
            amount_minor=bad,
            entry_date=DAY,
            idempotency_key="o",  # type: ignore[arg-type]
        )
    assert counts(world.conn) == dict.fromkeys(TABLES, 0)


@pytest.mark.parametrize("bad", [0, -1])
def test_non_positive_amounts_raise_value_error(world: World, bad: int) -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        expense(world, "e", bad)
    with pytest.raises(ValueError):
        world.svc.record_income(
            dest_account_id=world.bank_a, category_id=world.salary, amount_minor=bad, tx_date=DAY,
            idempotency_key="i",
        )  # fmt: skip
    with pytest.raises(ValueError):
        world.svc.record_transfer(
            from_account_id=world.bank_a, to_account_id=world.bank_b, amount_minor=bad, tx_date=DAY,
            idempotency_key="t",
        )  # fmt: skip


def test_opening_balance_zero_rejected(world: World) -> None:
    with pytest.raises(ValueError, match="non-zero"):
        world.svc.record_opening_balance(
            account_id=world.bank_a, amount_minor=0, entry_date=DAY, idempotency_key="o"
        )


def test_split_validation(world: World) -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        expense(world, "e", 1000, splits=[SplitShareSpec("A", None, 600), SplitShareSpec("B", None, 401)])
    with pytest.raises(TypeError):
        expense(world, "e", 1000, splits=[SplitShareSpec("A", None, 1.5)])  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        expense(world, "e", 1000, splits=[SplitShareSpec("A", None, 0)])
    assert counts(world.conn) == dict.fromkeys(TABLES, 0)


def test_transfer_same_account_rejected(world: World) -> None:
    with pytest.raises(ValueError, match="same account"):
        world.svc.record_transfer(
            from_account_id=world.bank_a, to_account_id=world.bank_a, amount_minor=1, tx_date=DAY,
            idempotency_key="t",
        )  # fmt: skip


def test_unknown_or_wrong_accounts_and_categories(world: World) -> None:
    with pytest.raises(ValueError, match="Unknown account"):
        expense(world, "e", account="nope")
    with pytest.raises(ValueError, match="cannot be used"):
        expense(world, "e", account=world.dining_ledger)
    with pytest.raises(ValueError, match="Category must be of type"):
        world.svc.record_expense(
            source_account_id=world.bank_a, category_id=world.salary, amount_minor=1, tx_date=DAY,
            idempotency_key="e",
        )  # fmt: skip
    with pytest.raises(ValueError, match="Unknown category"):
        world.svc.record_income(
            dest_account_id=world.bank_a, category_id="nope", amount_minor=1, tx_date=DAY,
            idempotency_key="i",
        )  # fmt: skip
    assert counts(world.conn) == dict.fromkeys(TABLES, 0)


def test_refund_limits(world: World) -> None:
    original = world.svc.record_expense(
        source_account_id=world.bank_a, category_id=world.dining, amount_minor=1200, tx_date=DAY,
        idempotency_key="e", splits=[SplitShareSpec("A", None, 800)],
    )  # fmt: skip

    def refund(amount: int, key: str) -> str:
        return world.svc.record_refund(
            dest_account_id=world.bank_a,
            original_transaction_id=original,
            amount_minor=amount,
            tx_date=DAY,
            idempotency_key=key,
        )

    with pytest.raises(ValueError, match="Refund exceeds"):
        refund(401, "r1")  # user share is 400
    refund(300, "r2")
    with pytest.raises(ValueError, match="Refund exceeds"):
        refund(101, "r3")  # cumulative
    refund(100, "r4")
    with pytest.raises(ValueError, match="Unknown original"):
        world.svc.record_refund(
            dest_account_id=world.bank_a, original_transaction_id="nope", amount_minor=1, tx_date=DAY,
            idempotency_key="r5",
        )  # fmt: skip


def test_refund_of_non_expense_rejected(world: World) -> None:
    transfer = world.svc.record_transfer(
        from_account_id=world.bank_a, to_account_id=world.bank_b, amount_minor=10, tx_date=DAY,
        idempotency_key="t",
    )  # fmt: skip
    with pytest.raises(ValueError, match="not a refundable expense"):
        world.svc.record_refund(
            dest_account_id=world.bank_a, original_transaction_id=transfer, amount_minor=1, tx_date=DAY,
            idempotency_key="r",
        )  # fmt: skip


def test_empty_idempotency_key_rejected(world: World) -> None:
    with pytest.raises(ValueError, match="idempotency_key"):
        expense(world, "")


# ------------------------------------------------------------------ atomicity


def test_failure_after_lines_leaves_no_rows(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    expense(world, "seed", 1000)
    before = counts(world.conn)
    balances = [
        tuple(r) for r in world.conn.execute("SELECT id, current_balance_minor FROM accounts ORDER BY id")
    ]

    def boom(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("forced")

    monkeypatch.setattr(LedgerService, "_insert_transaction", boom)
    with pytest.raises(RuntimeError):
        expense(world, "k", 5000, splits=[SplitShareSpec("A", None, 100)])
    monkeypatch.undo()
    assert counts(world.conn) == before
    after = [
        tuple(r) for r in world.conn.execute("SELECT id, current_balance_minor FROM accounts ORDER BY id")
    ]
    assert after == balances
    assert not world.conn.in_transaction
    assert expense(world, "k", 5000)  # key was not consumed by the failed attempt


def test_failure_in_split_insert_rolls_back_everything(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("forced")

    monkeypatch.setattr(LedgerService, "_insert_splits", boom)
    with pytest.raises(RuntimeError):
        expense(world, "k", 5000, splits=[SplitShareSpec("A", None, 100)])
    monkeypatch.undo()
    assert counts(world.conn) == dict.fromkeys(TABLES, 0)
    assert world.svc.account_balance(world.bank_a) == 0
    assert (
        world.conn.execute(
            "SELECT current_balance_minor FROM accounts WHERE id = ?", (world.bank_a,)
        ).fetchone()[0]
        == 0
    )


def test_failure_in_settlement_rolls_back(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    _, split_ids = split_expense(world)
    before = counts(world.conn)

    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("forced")

    monkeypatch.setattr(LedgerService, "_apply_settlement", boom)
    with pytest.raises(RuntimeError):
        settle(world, split_ids[0], 100, "s")
    monkeypatch.undo()
    assert counts(world.conn) == before
    assert world.svc.verify_integrity().is_clean


# ---------------------------------------------------------- split settlement


def test_partial_then_full_settlement(world: World) -> None:
    _, split_ids = split_expense(world)
    first = settle(world, split_ids[0], 15000, "s1")
    row = world.conn.execute(
        "SELECT settled_amount_minor, status, settlement_transaction_id "
        "FROM reimbursable_splits WHERE id = ?",
        (split_ids[0],),
    ).fetchone()
    assert tuple(row) == (15000, "PARTIAL", first)
    with pytest.raises(ValueError, match="exceeds"):
        settle(world, split_ids[0], 25001, "s-over")
    second = settle(world, split_ids[0], 25000, "s2")
    row = world.conn.execute(
        "SELECT settled_amount_minor, status, settlement_transaction_id "
        "FROM reimbursable_splits WHERE id = ?",
        (split_ids[0],),
    ).fetchone()
    assert tuple(row) == (40000, "SETTLED", second)
    with pytest.raises(ValueError, match="not open"):
        settle(world, split_ids[0], 1, "s3")
    assert world.svc.account_balance(seed.PENDING_REIMBURSEMENTS_ACCOUNT_ID) == 40000
    assert world.svc.verify_integrity().is_clean


def test_settle_unknown_split(world: World) -> None:
    with pytest.raises(ValueError, match="Unknown split"):
        settle(world, "nope", 1, "s")


# -------------------------------------------------------------------- reversal


def test_reversal_restores_balances(world: World) -> None:
    tx, _ = split_expense(world)
    snapshot_before = {
        r[0]: r[1] for r in world.conn.execute("SELECT id, current_balance_minor FROM accounts")
    }
    assert snapshot_before[world.bank_a] == -120000
    rev = world.svc.reverse_entry(
        journal_entry_id=entry_id(world.conn, tx), entry_date=DAY, idempotency_key="rev"
    )
    balances = {r[0]: r[1] for r in world.conn.execute("SELECT id, current_balance_minor FROM accounts")}
    assert all(v == 0 for v in balances.values())
    original = world.conn.execute("SELECT review_status FROM transactions WHERE id = ?", (tx,)).fetchone()[0]
    assert original == "SUPERSEDED"
    row = world.conn.execute(
        "SELECT entry_type, reverses_journal_entry_id FROM journal_entries WHERE id = ?",
        (entry_id(world.conn, rev),),
    ).fetchone()
    assert tuple(row) == ("REVERSAL", entry_id(world.conn, tx))
    assert {r[0] for r in world.conn.execute("SELECT status FROM reimbursable_splits")} == {"WRITTEN_OFF"}
    assert world.svc.verify_integrity().is_clean


def test_reversal_rejections(world: World) -> None:
    tx = expense(world, "e")
    entry = entry_id(world.conn, tx)
    rev = world.svc.reverse_entry(journal_entry_id=entry, entry_date=DAY, idempotency_key="rev1")
    with pytest.raises(ValueError, match="already been reversed"):
        world.svc.reverse_entry(journal_entry_id=entry, entry_date=DAY, idempotency_key="rev2")
    with pytest.raises(ValueError, match="cannot be reversed"):
        world.svc.reverse_entry(
            journal_entry_id=entry_id(world.conn, rev), entry_date=DAY, idempotency_key="rev3"
        )
    with pytest.raises(ValueError, match="Unknown"):
        world.svc.reverse_entry(journal_entry_id="nope", entry_date=DAY, idempotency_key="rev4")


def test_reversal_blocked_by_refund_or_settlement(world: World) -> None:
    tx = expense(world, "e", 1000)
    refund = world.svc.record_refund(
        dest_account_id=world.bank_a, original_transaction_id=tx, amount_minor=100, tx_date=DAY,
        idempotency_key="r",
    )  # fmt: skip
    with pytest.raises(ValueError, match="refunds"):
        world.svc.reverse_entry(
            journal_entry_id=entry_id(world.conn, tx), entry_date=DAY, idempotency_key="x1"
        )
    world.svc.reverse_entry(
        journal_entry_id=entry_id(world.conn, refund), entry_date=DAY, idempotency_key="x2"
    )
    world.svc.reverse_entry(journal_entry_id=entry_id(world.conn, tx), entry_date=DAY, idempotency_key="x3")

    split_tx, split_ids = split_expense(world)
    settle(world, split_ids[0], 5, "s")
    with pytest.raises(ValueError, match="settled"):
        world.svc.reverse_entry(
            journal_entry_id=entry_id(world.conn, split_tx), entry_date=DAY, idempotency_key="x4"
        )


def test_reversed_refund_frees_refundable_amount(world: World) -> None:
    tx = expense(world, "e", 1000)
    refund = world.svc.record_refund(
        dest_account_id=world.bank_a, original_transaction_id=tx, amount_minor=1000, tx_date=DAY,
        idempotency_key="r1",
    )  # fmt: skip
    world.svc.reverse_entry(
        journal_entry_id=entry_id(world.conn, refund), entry_date=DAY, idempotency_key="x"
    )
    world.svc.record_refund(
        dest_account_id=world.bank_a, original_transaction_id=tx, amount_minor=1000, tx_date=DAY,
        idempotency_key="r2",
    )  # fmt: skip
    assert class_total(world.conn, "EXPENSE") == 0


def test_reversed_expense_cannot_be_refunded_or_settled(world: World) -> None:
    tx, split_ids = split_expense(world)
    world.svc.reverse_entry(journal_entry_id=entry_id(world.conn, tx), entry_date=DAY, idempotency_key="x")
    with pytest.raises(ValueError, match="not a refundable"):
        world.svc.record_refund(
            dest_account_id=world.bank_a, original_transaction_id=tx, amount_minor=1, tx_date=DAY,
            idempotency_key="r",
        )  # fmt: skip
    with pytest.raises(ValueError, match="not open"):
        settle(world, split_ids[0], 1, "s")


# --------------------------------------------------------------------- chart


def test_create_category_makes_backing_ledger_account(world: World) -> None:
    row = world.conn.execute(
        "SELECT a.account_class, a.account_subtype FROM categories c JOIN accounts a "
        "ON a.id = c.ledger_account_id WHERE c.id = ?",
        (world.dining,),
    ).fetchone()
    assert tuple(row) == ("EXPENSE", "SYSTEM_CATEGORY")


def test_create_category_rejects_unbacked_types(world: World) -> None:
    before = world.conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    with pytest.raises(ValueError):
        chart.create_category(world.conn, name="X", category_type="TRANSFER")
    assert world.conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == before


def test_create_category_failure_leaves_no_orphan_account(world: World) -> None:
    before = world.conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):
        chart.create_category(world.conn, name="X", category_type="EXPENSE", default_tax_section="BOGUS")
    assert world.conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == before


# ------------------------------------------------------- review round 1 additions


def other_category(w: World, name: str = "Travel") -> tuple[str, str]:
    return chart.create_category(w.conn, name=name, category_type="EXPENSE")


def test_income_cannot_be_refunded(world: World) -> None:
    income = world.svc.record_income(
        dest_account_id=world.bank_a,
        category_id=world.salary,
        amount_minor=1000,
        tx_date=DAY,
        idempotency_key="i",
    )
    with pytest.raises(ValueError, match="not a refundable expense"):
        world.svc.record_refund(
            dest_account_id=world.bank_a,
            original_transaction_id=income,
            amount_minor=100,
            tx_date=DAY,
            idempotency_key="r",
        )
    assert class_total(world.conn, "INCOME") == -1000


def test_idempotency_key_reused_with_different_arguments_conflicts(world: World) -> None:
    w = world
    first = expense(w, "k", 100)
    before = counts(w.conn)
    with pytest.raises(IdempotencyConflictError, match="different arguments"):
        expense(w, "k", 99999)
    with pytest.raises(IdempotencyConflictError):
        w.svc.record_income(
            dest_account_id=w.bank_a, category_id=w.salary, amount_minor=5, tx_date=DAY, idempotency_key="k"
        )
    with pytest.raises(IdempotencyConflictError):
        expense(w, "k", 100, account=w.bank_b)
    assert expense(w, "k", 100) == first
    assert counts(w.conn) == before
    assert issubclass(IdempotencyConflictError, ValueError)


def test_idempotency_conflicts_for_every_other_method(world: World) -> None:
    w = world
    open_args = {"account_id": w.bank_a, "entry_date": DAY, "idempotency_key": "o"}
    w.svc.record_opening_balance(amount_minor=500, **open_args)
    with pytest.raises(IdempotencyConflictError):
        w.svc.record_opening_balance(amount_minor=501, **open_args)
    kwargs = {"from_account_id": w.bank_a, "to_account_id": w.bank_b, "tx_date": DAY, "idempotency_key": "t"}
    w.svc.record_transfer(amount_minor=10, **kwargs)
    with pytest.raises(IdempotencyConflictError):
        w.svc.record_transfer(amount_minor=11, **kwargs)
    base = expense(w, "base", 1000)
    refund = {"dest_account_id": w.bank_a, "original_transaction_id": base, "tx_date": DAY}
    w.svc.record_refund(amount_minor=100, idempotency_key="rf", **refund)
    with pytest.raises(IdempotencyConflictError):
        w.svc.record_refund(amount_minor=200, idempotency_key="rf", **refund)
    _, split_ids = split_expense(w)
    settle(w, split_ids[0], 100, "st")
    with pytest.raises(IdempotencyConflictError):
        settle(w, split_ids[0], 200, "st")
    other = entry_id(w.conn, expense(w, "other", 7))
    to_reverse = expense(w, "to-reverse", 9)
    w.svc.reverse_entry(journal_entry_id=entry_id(w.conn, to_reverse), entry_date=DAY, idempotency_key="rv")
    with pytest.raises(IdempotencyConflictError):
        w.svc.reverse_entry(journal_entry_id=other, entry_date=DAY, idempotency_key="rv")
    assert w.svc.verify_integrity().is_clean


def test_recategorize_idempotency_and_conflict(world: World) -> None:
    w = world
    travel, _ = other_category(w)
    tx = expense(w, "e", 1000)
    w.svc.recategorize(tx, travel, DAY, "rc")
    before = counts(w.conn)
    assert w.svc.recategorize(tx, travel, DAY, "rc") == tx
    assert counts(w.conn) == before
    third, _ = other_category(w, "Fuel")
    with pytest.raises(IdempotencyConflictError):
        w.svc.recategorize(tx, third, DAY, "rc")
    with pytest.raises(IdempotencyConflictError):
        w.svc.recategorize(tx, travel, date(2027, 1, 1), "rc")


def test_inactive_account_rejected(world: World) -> None:
    world.conn.execute("UPDATE accounts SET is_active = 0 WHERE id = ?", (world.bank_a,))
    with pytest.raises(ValueError, match="Account is inactive"):
        expense(world, "e")
    with pytest.raises(ValueError, match="Account is inactive"):
        world.svc.record_transfer(
            from_account_id=world.bank_b,
            to_account_id=world.bank_a,
            amount_minor=1,
            tx_date=DAY,
            idempotency_key="t",
        )
    assert counts(world.conn) == dict.fromkeys(TABLES, 0)


def test_replay_still_works_after_account_deactivated(world: World) -> None:
    first = expense(world, "e")
    world.conn.execute("UPDATE accounts SET is_active = 0 WHERE id = ?", (world.bank_a,))
    assert expense(world, "e") == first


def test_amount_upper_bound(world: World) -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        expense(world, "e", MAX_AMOUNT_MINOR + 1)
    with pytest.raises(ValueError, match="must not exceed"):
        world.svc.record_opening_balance(
            account_id=world.bank_a,
            amount_minor=-(MAX_AMOUNT_MINOR + 1),
            entry_date=DAY,
            idempotency_key="o",
        )
    with pytest.raises(ValueError, match="must not exceed"):
        expense(world, "e", 10, splits=[SplitShareSpec("A", None, MAX_AMOUNT_MINOR + 1)])
    for key in ("i1", "i2"):
        world.svc.record_income(
            dest_account_id=world.bank_a,
            category_id=world.salary,
            amount_minor=MAX_AMOUNT_MINOR,
            tx_date=DAY,
            idempotency_key=key,
        )
    assert world.svc.verify_integrity().is_clean


def test_cached_balance_overflow_rolls_back(world: World) -> None:
    world.conn.execute(
        "UPDATE accounts SET current_balance_minor = ? WHERE id = ?", (2**63 - 1 - 5, world.bank_a)
    )
    before = counts(world.conn)
    with pytest.raises(ValueError, match="supported range"):
        world.svc.record_income(
            dest_account_id=world.bank_a,
            category_id=world.salary,
            amount_minor=10,
            tx_date=DAY,
            idempotency_key="i",
        )
    assert counts(world.conn) == before
    ledger_balance = world.conn.execute(
        "SELECT current_balance_minor FROM accounts WHERE id = ?", (world.salary_ledger,)
    ).fetchone()[0]
    assert ledger_balance == 0


def test_reversal_rows_are_both_superseded(world: World) -> None:
    tx = expense(world, "e")
    entry = entry_id(world.conn, tx)
    rev = world.svc.reverse_entry(journal_entry_id=entry, entry_date=DAY, idempotency_key="x")
    rows = world.conn.execute(
        "SELECT review_status FROM transactions WHERE id IN (?, ?)", (tx, rev)
    ).fetchall()
    assert [r[0] for r in rows] == ["SUPERSEDED", "SUPERSEDED"]
    live = world.conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE review_status != 'SUPERSEDED'"
    ).fetchone()[0]
    assert live == 0


def category_balances(w: World) -> dict[str, int]:
    return {
        r[0]: r[1]
        for r in w.conn.execute(
            "SELECT id, current_balance_minor FROM accounts WHERE account_subtype = 'SYSTEM_CATEGORY'"
        )
    }


def test_reverse_after_recategorizing_twice_zeroes_every_category(world: World) -> None:
    travel, _ = other_category(world)
    fuel, _ = other_category(world, "Fuel")
    tx, _ = split_expense(world)
    world.svc.recategorize(tx, travel, DAY, "rc1")
    world.svc.recategorize(tx, fuel, DAY, "rc2")
    entry = entry_id(world.conn, tx)
    world.svc.reverse_entry(journal_entry_id=entry, entry_date=DAY, idempotency_key="x")
    assert set(category_balances(world).values()) == {0}
    assert world.svc.account_balance(world.bank_a) == 0
    assert world.svc.verify_integrity().is_clean


def test_reverse_after_recategorizing_income(world: World) -> None:
    bonus, _ = chart.create_category(world.conn, name="Bonus", category_type="INCOME")
    tx = world.svc.record_income(
        dest_account_id=world.bank_a,
        category_id=world.salary,
        amount_minor=700,
        tx_date=DAY,
        idempotency_key="i",
    )
    world.svc.recategorize(tx, bonus, DAY, "rc")
    world.svc.reverse_entry(journal_entry_id=entry_id(world.conn, tx), entry_date=DAY, idempotency_key="x")
    assert set(category_balances(world).values()) == {0}
    assert world.svc.verify_integrity().is_clean


def test_partial_settlement_blocks_reversal(world: World) -> None:
    tx, split_ids = split_expense(world)
    settle(world, split_ids[0], 15000, "s1")
    status = world.conn.execute(
        "SELECT status FROM reimbursable_splits WHERE id = ?", (split_ids[0],)
    ).fetchone()[0]
    assert status == "PARTIAL"
    with pytest.raises(ValueError, match="settled"):
        world.svc.reverse_entry(
            journal_entry_id=entry_id(world.conn, tx), entry_date=DAY, idempotency_key="x"
        )
    assert world.svc.verify_integrity().is_clean


def test_failure_inside_caller_transaction_leaves_no_draft_or_stale_balance(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("forced")

    monkeypatch.setattr(LedgerService, "_insert_transaction", boom)
    with transaction(world.conn):
        with pytest.raises(RuntimeError):
            expense(world, "k", 5000, splits=[SplitShareSpec("A", None, 100)])
        monkeypatch.undo()
        expense(world, "ok", 300)  # the caller carries on and commits
    drafts = world.conn.execute("SELECT COUNT(*) FROM journal_entries WHERE status = 'DRAFT'").fetchone()[0]
    assert drafts == 0
    assert world.conn.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0] == 1
    assert world.svc.account_balance(world.bank_a) == -300
    assert world.svc.verify_integrity().is_clean


def test_replay_after_recategorize_is_not_a_conflict(world: World) -> None:
    travel, _ = other_category(world)
    tx = expense(world, "e", 1000)
    world.svc.recategorize(tx, travel, DAY, "rc")
    before = counts(world.conn)
    assert expense(world, "e", 1000) == tx
    assert counts(world.conn) == before
    other, _ = other_category(world, "Fuel")
    with pytest.raises(IdempotencyConflictError):
        world.svc.record_expense(
            source_account_id=world.bank_a,
            category_id=other,
            amount_minor=1000,
            tx_date=DAY,
            idempotency_key="e",
        )


def test_opening_balance_direction_is_statement_view_and_idempotent(world: World) -> None:
    args = {"entry_date": DAY}
    pos = world.svc.record_opening_balance(
        account_id=world.bank_a, amount_minor=500, idempotency_key="op", **args
    )
    neg = world.svc.record_opening_balance(
        account_id=world.card, amount_minor=-300, idempotency_key="on", **args
    )
    directions = {
        r[0]: r[1]
        for r in world.conn.execute("SELECT id, direction FROM transactions WHERE id IN (?, ?)", (pos, neg))
    }
    assert directions == {pos: "CREDIT", neg: "DEBIT"}
    assert world.svc.account_balance(world.bank_a) == 500
    assert world.svc.account_balance(world.card) == -300
    before = counts(world.conn)
    assert (
        world.svc.record_opening_balance(
            account_id=world.bank_a, amount_minor=500, idempotency_key="op", **args
        )
        == pos
    )
    assert (
        world.svc.record_opening_balance(
            account_id=world.card, amount_minor=-300, idempotency_key="on", **args
        )
        == neg
    )
    assert counts(world.conn) == before
    with pytest.raises(IdempotencyConflictError):
        world.svc.record_opening_balance(
            account_id=world.card, amount_minor=300, idempotency_key="on", **args
        )
    rev = world.svc.reverse_entry(
        journal_entry_id=entry_id(world.conn, pos), entry_date=DAY, idempotency_key="rv"
    )
    assert (
        world.conn.execute("SELECT direction FROM transactions WHERE id = ?", (rev,)).fetchone()[0] == "DEBIT"
    )
    assert world.svc.verify_integrity().is_clean
