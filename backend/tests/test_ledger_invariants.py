"""Property tests: random operation sequences must keep the ledger balanced and caches fresh."""

import sqlite3
import tempfile
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.database.migrate import apply_migrations
from app.database.seed import seed_system_accounts
from app.database.session import connect
from app.finance import chart
from app.finance.ledger_service import LedgerService, SplitShareSpec

BASE_DAY = date(2026, 1, 1)
TABLES = ("journal_entries", "journal_lines", "transactions", "reimbursable_splits")
KINDS = ("opening", "expense", "income", "transfer", "refund", "settle", "reverse", "recategorize")

operations = st.lists(
    st.tuples(
        st.sampled_from(KINDS),
        st.integers(0, 5),
        st.integers(0, 5),
        st.integers(1, 10_000_000),
        st.integers(-1, 3),
    ),
    min_size=1,
    max_size=18,
)


class Sandbox:
    """A fresh database plus the dynamic state needed to aim operations at earlier results."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.svc = LedgerService(conn)
        mk = chart.create_account
        self.funding = [
            mk(conn, name="A", account_class="ASSET", account_subtype="BANK_SAVINGS"),
            mk(conn, name="B", account_class="ASSET", account_subtype="BANK_CURRENT"),
            mk(conn, name="C", account_class="LIABILITY", account_subtype="CREDIT_CARD"),
            mk(conn, name="W", account_class="ASSET", account_subtype="WALLET"),
        ]
        self.expense_cats = [
            chart.create_category(conn, name=n, category_type="EXPENSE")[0] for n in ("Food", "Rent", "Fuel")
        ]
        self.income_cat = chart.create_category(conn, name="Pay", category_type="INCOME")[0]
        self.expense_txs: list[str] = []
        self.split_ids: list[str] = []
        self.entry_ids: list[str] = []
        self.replays: list[Callable[[], str]] = []
        self.results: list[str] = []

    def _entry_id(self, tx_id: str) -> str:
        return self.conn.execute(
            "SELECT journal_entry_id FROM transactions WHERE id = ?", (tx_id,)
        ).fetchone()[0]

    def _splits_for(self, amount: int, flag: int) -> list[SplitShareSpec] | None:
        if flag == 1:
            return [SplitShareSpec("P1", None, max(1, amount // 2))] if amount >= 2 else None
        if flag == 2:
            return [SplitShareSpec("P1", "p1@upi", amount)]
        if flag == 3:
            return [
                SplitShareSpec("P1", None, max(1, amount // 3)),
                SplitShareSpec("P2", None, max(1, amount // 3)),
            ]
        return None

    def _calls(self, idx: int, op: tuple[str, int, int, int, int]) -> Callable[[], str] | None:
        kind, i, j, amount, flag = op
        key = f"op-{idx}"
        day = BASE_DAY + timedelta(days=idx)
        svc, acct = self.svc, self.funding
        a, b = acct[i % len(acct)], acct[j % len(acct)]
        if kind == "opening":
            signed = amount if flag >= 0 else -amount
            return lambda: svc.record_opening_balance(
                account_id=a, amount_minor=signed, entry_date=day, idempotency_key=key
            )
        if kind == "expense":
            cat, splits = self.expense_cats[j % 3], self._splits_for(amount, flag)
            return lambda: svc.record_expense(
                source_account_id=a, category_id=cat, amount_minor=amount, tx_date=day,
                idempotency_key=key, splits=splits,
            )  # fmt: skip
        if kind == "income":
            return lambda: svc.record_income(
                dest_account_id=a, category_id=self.income_cat, amount_minor=amount, tx_date=day,
                idempotency_key=key,
            )  # fmt: skip
        if kind == "transfer":
            return lambda: svc.record_transfer(
                from_account_id=a, to_account_id=b, amount_minor=amount, tx_date=day, idempotency_key=key
            )
        return self._dynamic_call(kind, key, day, a, i, amount)

    def _dynamic_call(
        self, kind: str, key: str, day: date, a: str, i: int, amount: int
    ) -> Callable[[], str] | None:
        svc = self.svc
        if kind == "refund" and self.expense_txs:
            target = self.expense_txs[i % len(self.expense_txs)]
            share = self.conn.execute(
                "SELECT user_share_minor FROM transactions WHERE id = ?", (target,)
            ).fetchone()[0]
            amt = min(amount, max(1, share))
            return lambda: svc.record_refund(
                dest_account_id=a, original_transaction_id=target, amount_minor=amt, tx_date=day,
                idempotency_key=key,
            )  # fmt: skip
        if kind == "settle" and self.split_ids:
            split = self.split_ids[i % len(self.split_ids)]
            owed = self.conn.execute(
                "SELECT owed_amount_minor FROM reimbursable_splits WHERE id = ?", (split,)
            ).fetchone()[0]
            amt = max(1, min(amount, owed))
            return lambda: svc.settle_split(
                split_id=split, bank_account_id=a, amount_minor=amt, tx_date=day, idempotency_key=key
            )
        if kind == "reverse" and self.entry_ids:
            entry = self.entry_ids[i % len(self.entry_ids)]
            return lambda: svc.reverse_entry(journal_entry_id=entry, entry_date=day, idempotency_key=key)
        if kind == "recategorize" and self.expense_txs:
            target = self.expense_txs[i % len(self.expense_txs)]
            category = self.expense_cats[amount % len(self.expense_cats)]
            return lambda: svc.recategorize(target, category, day, key)
        return None

    def apply(self, idx: int, op: tuple[str, int, int, int, int]) -> None:
        call = self._calls(idx, op)
        if call is None:
            return
        entries_before = self.conn.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0]
        try:
            tx_id = call()
        except ValueError:
            return  # a legitimately rejected operation must leave no trace; integrity is checked at the end
        entries_after = self.conn.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0]
        if entries_after > entries_before:  # a same-category recategorize is a keyless no-op, not replayable
            self.replays.append(call)
        if entries_after > entries_before:
            self.results.append(tx_id)
        row = self.conn.execute(
            "SELECT t.id, t.journal_entry_id, e.entry_type FROM transactions t "
            "JOIN journal_entries e ON e.id = t.journal_entry_id WHERE t.id = ?",
            (tx_id,),
        ).fetchone()
        self.entry_ids.append(row["journal_entry_id"])
        if row["entry_type"] in ("STANDARD", "SPLIT_EXPENSE") and op[0] == "expense":
            self.expense_txs.append(tx_id)
            self.split_ids.extend(
                r[0]
                for r in self.conn.execute(
                    "SELECT id FROM reimbursable_splits WHERE transaction_id = ?", (tx_id,)
                )
            )

    def snapshot(self) -> tuple[dict[str, int], list[tuple[str, int]]]:
        counts = {t: self.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}  # noqa: S608
        balances = [
            tuple(r) for r in self.conn.execute("SELECT id, current_balance_minor FROM accounts ORDER BY id")
        ]
        return counts, balances


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(ops=operations)
def test_random_sequences_keep_ledger_consistent(ops: list[tuple[str, int, int, int, int]]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        conn = connect(Path(tmp) / "prop.db")
        try:
            conn.execute("PRAGMA synchronous = OFF")  # test-only speed-up; durability is irrelevant here
            apply_migrations(conn)
            seed_system_accounts(conn)
            box = Sandbox(conn)
            for idx, op in enumerate(ops):
                box.apply(idx, op)

            report = box.svc.verify_integrity()
            assert report.global_sum_minor == 0
            assert report.unbalanced_entry_ids == ()
            assert report.accounts_with_stale_cached_balance == ()

            before = box.snapshot()
            replayed = [call() for call in box.replays]
            assert replayed == box.results
            assert box.snapshot() == before
            assert box.svc.verify_integrity().is_clean
        finally:
            conn.close()
