"""Double-entry ledger service.

Every write method runs in a single transaction, is idempotent on its key, and posts a balanced
journal entry (DRAFT -> lines -> POSTED) together with its operational ``transactions`` row.
Convention: ``accounts.current_balance_minor`` equals the sum of that account's posted signed
lines (debit positive), so liabilities and income accounts run negative.
"""

import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from app.database import seed
from app.database.session import transaction

_FUNDING_CLASSES = ("ASSET", "LIABILITY")
_NON_FUNDING_SUBTYPES = ("REIMBURSEMENT_CLEARING", "OPENING_EQUITY", "SYSTEM_CATEGORY")
_EXPENSE_ENTRY_TYPES = ("STANDARD", "SPLIT_EXPENSE")
MAX_AMOUNT_MINOR = 10**15
_INT64_MAX = 2**63 - 1
_LINE_PREFIX = "line:"
_CONFLICT_MESSAGE = "Idempotency key reused with different arguments."


class IdempotencyConflictError(ValueError):
    """An idempotency key was replayed with arguments that differ from the original call."""


@dataclass(frozen=True)
class SplitShareSpec:
    counterparty_name: str
    counterparty_vpa: str | None
    owed_amount_minor: int


@dataclass(frozen=True)
class LineSpec:
    account_id: str
    signed_amount_minor: int
    memo: str | None = None


@dataclass(frozen=True)
class EntryMeta:
    statement_id: str | None = None
    external_reference: str | None = None
    dedup_fingerprint: str | None = None
    description: str | None = None
    clean_description: str | None = None
    merchant_id: str | None = None
    is_provisional: bool = False


@dataclass(frozen=True)
class TxSpec:
    account_id: str
    counterparty_account_id: str
    amount_minor: int
    user_share_minor: int
    direction: str
    transaction_type: str
    category_id: str | None = None
    linked_transaction_id: str | None = None
    review_status: str | None = None


@dataclass(frozen=True)
class PostingPlan:
    entry_type: str
    entry_date: date
    idempotency_key: str
    lines: tuple[LineSpec, ...]
    tx: TxSpec
    meta: EntryMeta
    default_description: str
    reverses_journal_entry_id: str | None = None
    after: Callable[[str], None] | None = None


@dataclass(frozen=True)
class IntegrityReport:
    global_sum_minor: int
    unbalanced_entry_ids: tuple[str, ...]
    accounts_with_stale_cached_balance: tuple[str, ...]

    @property
    def is_clean(self) -> bool:
        return (
            self.global_sum_minor == 0
            and not self.unbalanced_entry_ids
            and not self.accounts_with_stale_cached_balance
        )


def _check_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int of minor units.")
    return value


def _check_amount(value: object, name: str = "amount_minor") -> int:
    _check_int(value, name)
    if value <= 0:  # type: ignore[operator]
        raise ValueError(f"{name} must be greater than zero.")
    _check_upper_bound(value, name)  # type: ignore[arg-type]
    return value  # type: ignore[return-value]


def _check_upper_bound(value: int, name: str) -> None:
    if abs(value) > MAX_AMOUNT_MINOR:
        raise ValueError(f"{name} must not exceed {MAX_AMOUNT_MINOR} minor units.")


def _check_date(value: object, name: str) -> date:
    if not isinstance(value, date):
        raise TypeError(f"{name} must be a date.")
    return value


def _check_splits(splits: list[SplitShareSpec] | None, total_minor: int) -> tuple[SplitShareSpec, ...]:
    specs = tuple(splits or ())
    for spec in specs:
        if not isinstance(spec, SplitShareSpec):
            raise TypeError("splits must contain SplitShareSpec items.")
        _check_amount(spec.owed_amount_minor, "owed_amount_minor")
    if sum(spec.owed_amount_minor for spec in specs) > total_minor:
        raise ValueError("Reimbursable split sum cannot exceed the total amount.")
    return specs


class LedgerService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ------------------------------------------------------------------ writes

    def record_opening_balance(
        self,
        *,
        account_id: str,
        amount_minor: int,
        entry_date: date,
        idempotency_key: str,
        statement_id: str | None = None,
        external_reference: str | None = None,
        dedup_fingerprint: str | None = None,
        description: str | None = None,
        clean_description: str | None = None,
        merchant_id: str | None = None,
        is_provisional: bool = False,
    ) -> str:
        _check_int(amount_minor, "amount_minor")
        if amount_minor == 0:
            raise ValueError("amount_minor must be non-zero.")
        _check_upper_bound(amount_minor, "amount_minor")
        _check_date(entry_date, "entry_date")
        meta = EntryMeta(
            statement_id, external_reference, dedup_fingerprint, description, clean_description,
            merchant_id, is_provisional,
        )  # fmt: skip

        def build() -> PostingPlan:
            self._require_funding_account(account_id)
            equity = seed.OPENING_EQUITY_ACCOUNT_ID
            return PostingPlan(
                entry_type="OPENING_BALANCE",
                entry_date=entry_date,
                idempotency_key=idempotency_key,
                lines=(LineSpec(account_id, amount_minor), LineSpec(equity, -amount_minor)),
                tx=TxSpec(
                    account_id,
                    equity,
                    abs(amount_minor),
                    0,
                    "DEBIT" if amount_minor > 0 else "CREDIT",
                    "TRANSFER",
                ),  # fmt: skip
                meta=meta,
                default_description="Opening balance",
            )

        return self._run(
            idempotency_key,
            build,
            {
                "e_type": "OPENING_BALANCE",
                "e_date": entry_date.isoformat(),
                "account_id": account_id,
                "amount_minor": abs(amount_minor),
                "direction": "DEBIT" if amount_minor > 0 else "CREDIT",
            },
        )

    def record_expense(
        self,
        *,
        source_account_id: str,
        category_id: str,
        amount_minor: int,
        tx_date: date,
        idempotency_key: str,
        splits: list[SplitShareSpec] | None = None,
        statement_id: str | None = None,
        external_reference: str | None = None,
        dedup_fingerprint: str | None = None,
        description: str | None = None,
        clean_description: str | None = None,
        merchant_id: str | None = None,
        is_provisional: bool = False,
    ) -> str:
        _check_amount(amount_minor)
        _check_date(tx_date, "tx_date")
        specs = _check_splits(splits, amount_minor)
        owed = sum(spec.owed_amount_minor for spec in specs)
        meta = EntryMeta(
            statement_id, external_reference, dedup_fingerprint, description, clean_description,
            merchant_id, is_provisional,
        )  # fmt: skip

        def build() -> PostingPlan:
            self._require_funding_account(source_account_id)
            ledger_id = self._category_ledger_account(category_id, "EXPENSE")
            user_share = amount_minor - owed
            lines = [LineSpec(source_account_id, -amount_minor)]
            if user_share > 0:
                lines.append(LineSpec(ledger_id, user_share, "User share"))
            if owed > 0:
                lines.append(LineSpec(seed.PENDING_REIMBURSEMENTS_ACCOUNT_ID, owed, "Pending reimbursements"))
            return PostingPlan(
                entry_type="SPLIT_EXPENSE" if specs else "STANDARD",
                entry_date=tx_date,
                idempotency_key=idempotency_key,
                lines=tuple(lines),
                tx=TxSpec(
                    source_account_id,
                    ledger_id,
                    amount_minor,
                    user_share,
                    "DEBIT",
                    "EXPENSE",
                    category_id=category_id,
                ),  # fmt: skip
                meta=meta,
                default_description="Expense",
                after=lambda tx_id: self._insert_splits(tx_id, specs),
            )

        identity = {
            "e_type": "SPLIT_EXPENSE" if specs else "STANDARD",
            "e_date": tx_date.isoformat(),
            "account_id": source_account_id,
            "amount_minor": amount_minor,
            "user_share_minor": amount_minor - owed,
            **self._ledger_line_identity(category_id, amount_minor - owed),
        }
        return self._run(idempotency_key, build, identity)

    def record_income(
        self,
        *,
        dest_account_id: str,
        category_id: str,
        amount_minor: int,
        tx_date: date,
        idempotency_key: str,
        statement_id: str | None = None,
        external_reference: str | None = None,
        dedup_fingerprint: str | None = None,
        description: str | None = None,
        clean_description: str | None = None,
        merchant_id: str | None = None,
        is_provisional: bool = False,
    ) -> str:
        _check_amount(amount_minor)
        _check_date(tx_date, "tx_date")
        meta = EntryMeta(
            statement_id, external_reference, dedup_fingerprint, description, clean_description,
            merchant_id, is_provisional,
        )  # fmt: skip

        def build() -> PostingPlan:
            self._require_funding_account(dest_account_id)
            ledger_id = self._category_ledger_account(category_id, "INCOME")
            return PostingPlan(
                entry_type="STANDARD",
                entry_date=tx_date,
                idempotency_key=idempotency_key,
                lines=(LineSpec(dest_account_id, amount_minor), LineSpec(ledger_id, -amount_minor)),
                tx=TxSpec(
                    dest_account_id,
                    ledger_id,
                    amount_minor,
                    amount_minor,
                    "CREDIT",
                    "INCOME",
                    category_id=category_id,
                ),  # fmt: skip
                meta=meta,
                default_description="Income",
            )

        identity = {
            "e_type": "STANDARD",
            "e_date": tx_date.isoformat(),
            "account_id": dest_account_id,
            "amount_minor": amount_minor,
            "transaction_type": "INCOME",
            **self._ledger_line_identity(category_id, -amount_minor),
        }
        return self._run(idempotency_key, build, identity)

    def record_transfer(
        self,
        *,
        from_account_id: str,
        to_account_id: str,
        amount_minor: int,
        tx_date: date,
        idempotency_key: str,
        statement_id: str | None = None,
        external_reference: str | None = None,
        dedup_fingerprint: str | None = None,
        description: str | None = None,
        clean_description: str | None = None,
        merchant_id: str | None = None,
        is_provisional: bool = False,
    ) -> str:
        _check_amount(amount_minor)
        _check_date(tx_date, "tx_date")
        if from_account_id == to_account_id:
            raise ValueError("Cannot transfer between the same account.")
        meta = EntryMeta(
            statement_id, external_reference, dedup_fingerprint, description, clean_description,
            merchant_id, is_provisional,
        )  # fmt: skip

        def build() -> PostingPlan:
            self._require_funding_account(from_account_id)
            to_row = self._require_funding_account(to_account_id)
            is_card = to_row["account_subtype"] == "CREDIT_CARD"
            return PostingPlan(
                entry_type="CARD_SETTLEMENT" if is_card else "INTERNAL_TRANSFER",
                entry_date=tx_date,
                idempotency_key=idempotency_key,
                lines=(LineSpec(to_account_id, amount_minor), LineSpec(from_account_id, -amount_minor)),
                tx=TxSpec(
                    from_account_id,
                    to_account_id,
                    amount_minor,
                    0,
                    "DEBIT",
                    "CARD_SETTLEMENT" if is_card else "TRANSFER",
                ),  # fmt: skip
                meta=meta,
                default_description="Card payment" if is_card else "Transfer",
            )

        identity = {
            "e_date": tx_date.isoformat(),
            "account_id": from_account_id,
            "counterparty_account_id": to_account_id,
            "amount_minor": amount_minor,
        }
        return self._run(idempotency_key, build, identity)

    def record_refund(
        self,
        *,
        dest_account_id: str,
        original_transaction_id: str,
        amount_minor: int,
        tx_date: date,
        idempotency_key: str,
        statement_id: str | None = None,
        external_reference: str | None = None,
        dedup_fingerprint: str | None = None,
        description: str | None = None,
        clean_description: str | None = None,
        merchant_id: str | None = None,
        is_provisional: bool = False,
    ) -> str:
        _check_amount(amount_minor)
        _check_date(tx_date, "tx_date")
        meta = EntryMeta(
            statement_id, external_reference, dedup_fingerprint, description, clean_description,
            merchant_id, is_provisional,
        )  # fmt: skip

        def build() -> PostingPlan:
            self._require_funding_account(dest_account_id)
            original = self._refundable_original(original_transaction_id, amount_minor)
            expense_account = original["counterparty_account_id"]
            return PostingPlan(
                entry_type="REFUND",
                entry_date=tx_date,
                idempotency_key=idempotency_key,
                lines=(LineSpec(dest_account_id, amount_minor), LineSpec(expense_account, -amount_minor)),
                tx=TxSpec(
                    dest_account_id,
                    expense_account,
                    amount_minor,
                    amount_minor,
                    "CREDIT",
                    "REFUND",
                    category_id=original["category_id"],
                    linked_transaction_id=original["id"],
                ),  # fmt: skip
                meta=meta,
                default_description="Refund",
            )

        identity = {
            "e_type": "REFUND",
            "e_date": tx_date.isoformat(),
            "account_id": dest_account_id,
            "amount_minor": amount_minor,
            "linked_transaction_id": original_transaction_id,
        }
        return self._run(idempotency_key, build, identity)

    def settle_split(
        self,
        *,
        split_id: str,
        bank_account_id: str,
        amount_minor: int,
        tx_date: date,
        idempotency_key: str,
        statement_id: str | None = None,
        external_reference: str | None = None,
        dedup_fingerprint: str | None = None,
        description: str | None = None,
        clean_description: str | None = None,
        merchant_id: str | None = None,
        is_provisional: bool = False,
    ) -> str:
        _check_amount(amount_minor)
        _check_date(tx_date, "tx_date")
        meta = EntryMeta(
            statement_id, external_reference, dedup_fingerprint, description, clean_description,
            merchant_id, is_provisional,
        )  # fmt: skip

        def build() -> PostingPlan:
            self._require_funding_account(bank_account_id)
            split = self._settleable_split(split_id, amount_minor)
            pending = seed.PENDING_REIMBURSEMENTS_ACCOUNT_ID
            return PostingPlan(
                entry_type="REIMBURSEMENT_SETTLEMENT",
                entry_date=tx_date,
                idempotency_key=idempotency_key,
                lines=(LineSpec(bank_account_id, amount_minor), LineSpec(pending, -amount_minor)),
                tx=TxSpec(bank_account_id, pending, amount_minor, 0, "CREDIT", "TRANSFER"),
                meta=meta,
                default_description=f"Reimbursement from {split['counterparty_name']}",
                after=lambda tx_id: self._apply_settlement(split, amount_minor, tx_id),
            )

        identity = {
            "e_type": "REIMBURSEMENT_SETTLEMENT",
            "e_date": tx_date.isoformat(),
            "account_id": bank_account_id,
            "amount_minor": amount_minor,
        }
        return self._run(idempotency_key, build, identity)

    def reverse_entry(self, *, journal_entry_id: str, entry_date: date, idempotency_key: str) -> str:
        _check_date(entry_date, "entry_date")
        identity = {
            "e_type": "REVERSAL",
            "e_date": entry_date.isoformat(),
            "e_reverses": journal_entry_id,
        }
        return self._run(
            idempotency_key,
            lambda: self._build_reversal(journal_entry_id, entry_date, idempotency_key),
            identity,
        )

    def recategorize(
        self, transaction_id: str, new_category_id: str, entry_date: date, idempotency_key: str
    ) -> str:
        """Move the user's share of an EXPENSE/INCOME transaction to another category.

        Posts a balanced STANDARD adjustment entry (no new ``transactions`` row) and repoints the
        transaction. Returns ``transaction_id``; the same category or a replayed key is a no-op.
        """
        _check_date(entry_date, "entry_date")
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise ValueError("idempotency_key must be a non-empty string.")
        with transaction(self.conn):
            adjustment = self.conn.execute(
                "SELECT id, entry_type, entry_date FROM journal_entries WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if adjustment is not None:
                self._check_adjustment_replay(adjustment, transaction_id, new_category_id, entry_date)
                return transaction_id
            original = self._recategorizable(transaction_id)
            if original["category_id"] == new_category_id:
                return transaction_id
            new_ledger = self._category_ledger_account(new_category_id, original["transaction_type"])
            old_ledger, share = original["counterparty_account_id"], original["user_share_minor"]
            if share > 0:
                moved = share if original["transaction_type"] == "EXPENSE" else -share
                lines = (
                    LineSpec(old_ledger, -moved, "Recategorized from"),
                    LineSpec(new_ledger, moved, "Recategorized to"),
                )
                self._post_adjustment(entry_date, idempotency_key, lines)
            self.conn.execute(
                "UPDATE transactions SET category_id = ?, counterparty_account_id = ?, "
                "updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
                (new_category_id, new_ledger, transaction_id),
            )
        return transaction_id

    def _check_adjustment_replay(
        self, entry: sqlite3.Row, transaction_id: str, new_category_id: str, entry_date: date
    ) -> None:
        tx = self.conn.execute(
            "SELECT transaction_type, user_share_minor FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
        if tx is None:
            raise IdempotencyConflictError(_CONFLICT_MESSAGE)
        new_ledger = self._category_ledger_account(new_category_id, tx["transaction_type"])
        moved = self.conn.execute(
            "SELECT 1 FROM journal_lines WHERE journal_entry_id = ? AND account_id = ? "
            "AND ABS(signed_amount_minor) = ?",
            (entry["id"], new_ledger, tx["user_share_minor"]),
        ).fetchone()
        if entry["entry_type"] != "STANDARD" or entry["entry_date"] != entry_date.isoformat() or not moved:
            raise IdempotencyConflictError(_CONFLICT_MESSAGE)

    # ------------------------------------------------------------------- reads

    def account_balance(self, account_id: str) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(l.signed_amount_minor), 0) AS bal FROM journal_lines l "
            "JOIN journal_entries e ON e.id = l.journal_entry_id "
            "WHERE e.status = 'POSTED' AND l.account_id = ?",
            (account_id,),
        ).fetchone()
        return int(row["bal"])

    def verify_integrity(self) -> IntegrityReport:
        # Summed per account (each bounded by the cached-balance guard) so SQLite never overflows.
        per_account = self.conn.execute(
            "SELECT SUM(l.signed_amount_minor) AS s FROM journal_lines l "
            "JOIN journal_entries e ON e.id = l.journal_entry_id WHERE e.status = 'POSTED' "
            "GROUP BY l.account_id"
        ).fetchall()
        total = sum(int(r["s"]) for r in per_account)
        unbalanced = self.conn.execute(
            "SELECT e.id FROM journal_entries e JOIN journal_lines l ON l.journal_entry_id = e.id "
            "WHERE e.status = 'POSTED' GROUP BY e.id HAVING SUM(l.signed_amount_minor) != 0 ORDER BY e.id"
        ).fetchall()
        stale = self.conn.execute(
            "SELECT a.id FROM accounts a WHERE a.current_balance_minor != COALESCE(("
            "SELECT SUM(l.signed_amount_minor) FROM journal_lines l "
            "JOIN journal_entries e ON e.id = l.journal_entry_id "
            "WHERE e.status = 'POSTED' AND l.account_id = a.id), 0) ORDER BY a.id"
        ).fetchall()
        return IntegrityReport(
            global_sum_minor=int(total),
            unbalanced_entry_ids=tuple(r["id"] for r in unbalanced),
            accounts_with_stale_cached_balance=tuple(r["id"] for r in stale),
        )

    # ----------------------------------------------------------------- posting

    def _run(
        self, idempotency_key: str, build: Callable[[], PostingPlan], identity: dict[str, object]
    ) -> str:
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise ValueError("idempotency_key must be a non-empty string.")
        with transaction(self.conn):
            existing = self.conn.execute(
                "SELECT t.*, e.entry_type AS e_type, e.entry_date AS e_date, "
                "e.reverses_journal_entry_id AS e_reverses FROM transactions t "
                "JOIN journal_entries e ON e.id = t.journal_entry_id WHERE e.idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing is None:
                return self._post_entry(build())
            if not self._matches_identity(existing, identity):
                raise IdempotencyConflictError(_CONFLICT_MESSAGE)
            return existing["id"]

    def _ledger_line_identity(self, category_id: str, signed_minor: int) -> dict[str, object]:
        """Identity entry for the category line as first posted (the tx row may be recategorized later)."""
        row = self.conn.execute(
            "SELECT ledger_account_id FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if row is None or signed_minor == 0:
            return {}
        return {f"{_LINE_PREFIX}{row['ledger_account_id']}": signed_minor}

    def _matches_identity(self, existing: sqlite3.Row, identity: dict[str, object]) -> bool:
        for key, expected in identity.items():
            if key.startswith(_LINE_PREFIX):
                found = self.conn.execute(
                    "SELECT 1 FROM journal_lines WHERE journal_entry_id = ? AND account_id = ? "
                    "AND signed_amount_minor = ?",
                    (existing["journal_entry_id"], key.removeprefix(_LINE_PREFIX), expected),
                ).fetchone()
                if found is None:
                    return False
            elif existing[key] != expected:
                return False
        return True

    def _post_entry(self, plan: PostingPlan) -> str:
        entry_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO journal_entries (id, entry_date, entry_type, source_statement_id, "
            "reverses_journal_entry_id, is_provisional, idempotency_key) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                entry_id,
                plan.entry_date.isoformat(),
                plan.entry_type,
                plan.meta.statement_id,
                plan.reverses_journal_entry_id,
                int(plan.meta.is_provisional),
                plan.idempotency_key,
            ),
        )
        for line in plan.lines:
            self._insert_line(entry_id, line)
        tx_id = self._insert_transaction(entry_id, plan)
        self.conn.execute("UPDATE journal_entries SET status = 'POSTED' WHERE id = ?", (entry_id,))
        if plan.after is not None:
            plan.after(tx_id)
        return tx_id

    def _post_adjustment(self, entry_date: date, idempotency_key: str, lines: tuple[LineSpec, ...]) -> None:
        entry_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO journal_entries (id, entry_date, entry_type, idempotency_key) "
            "VALUES (?, ?, 'STANDARD', ?)",
            (entry_id, entry_date.isoformat(), idempotency_key),
        )
        for line in lines:
            self._insert_line(entry_id, line)
        self.conn.execute("UPDATE journal_entries SET status = 'POSTED' WHERE id = ?", (entry_id,))

    def _recategorizable(self, transaction_id: str) -> sqlite3.Row:
        row = self.conn.execute(
            "SELECT t.id, t.category_id, t.counterparty_account_id, t.user_share_minor, t.transaction_type, "
            "t.review_status, e.entry_type FROM transactions t "
            "JOIN journal_entries e ON e.id = t.journal_entry_id WHERE t.id = ?",
            (transaction_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Unknown transaction.")
        if row["transaction_type"] not in ("EXPENSE", "INCOME") or row["entry_type"] not in (
            "STANDARD",
            "SPLIT_EXPENSE",
        ):
            raise ValueError("Only expense and income transactions can be recategorized.")
        if row["review_status"] == "SUPERSEDED":
            raise ValueError("A reversed transaction cannot be recategorized.")
        if self._exists(
            "SELECT 1 FROM transactions t JOIN journal_entries e ON e.id = t.journal_entry_id "
            "WHERE t.linked_transaction_id = ? AND e.entry_type = 'REFUND' "
            "AND t.review_status != 'SUPERSEDED'",
            transaction_id,
        ):
            raise ValueError("Reverse the refunds of this transaction first.")
        return row

    def _insert_line(self, entry_id: str, line: LineSpec) -> None:
        self.conn.execute(
            "INSERT INTO journal_lines (id, journal_entry_id, account_id, signed_amount_minor, memo) "
            "VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), entry_id, line.account_id, line.signed_amount_minor, line.memo),
        )
        balance = self.conn.execute(
            "SELECT current_balance_minor FROM accounts WHERE id = ?", (line.account_id,)
        ).fetchone()["current_balance_minor"]
        if abs(balance + line.signed_amount_minor) > _INT64_MAX:
            raise ValueError("Account balance would exceed the supported range.")
        self.conn.execute(
            "UPDATE accounts SET current_balance_minor = current_balance_minor + ?, "
            "updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
            (line.signed_amount_minor, line.account_id),
        )

    def _insert_transaction(self, entry_id: str, plan: PostingPlan) -> str:
        tx, meta = plan.tx, plan.meta
        tx_id = str(uuid.uuid4())
        description = meta.description or plan.default_description
        self.conn.execute(
            "INSERT INTO transactions (id, journal_entry_id, account_id, counterparty_account_id, "
            "statement_id, merchant_id, category_id, transaction_date, description, clean_description, "
            "external_reference, dedup_fingerprint, amount_minor, user_share_minor, direction, "
            "transaction_type, linked_transaction_id, review_status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tx_id,
                entry_id,
                tx.account_id,
                tx.counterparty_account_id,
                meta.statement_id,
                meta.merchant_id,
                tx.category_id,
                plan.entry_date.isoformat(),
                description,
                meta.clean_description or description,
                meta.external_reference,
                meta.dedup_fingerprint or plan.idempotency_key,
                tx.amount_minor,
                tx.user_share_minor,
                tx.direction,
                tx.transaction_type,
                tx.linked_transaction_id,
                tx.review_status or ("PROVISIONAL" if meta.is_provisional else "USER_APPROVED"),
            ),
        )
        return tx_id

    # ------------------------------------------------------------- validations

    def _require_funding_account(self, account_id: str) -> sqlite3.Row:
        row = self.conn.execute(
            "SELECT id, account_class, account_subtype, is_active FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Unknown account.")
        if not row["is_active"]:
            raise ValueError("Account is inactive.")
        if row["account_class"] not in _FUNDING_CLASSES or row["account_subtype"] in _NON_FUNDING_SUBTYPES:
            raise ValueError("Account cannot be used for this operation.")
        return row

    def _category_ledger_account(self, category_id: str, expected_type: str) -> str:
        row = self.conn.execute(
            "SELECT ledger_account_id, category_type FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Unknown category.")
        if row["category_type"] != expected_type:
            raise ValueError(f"Category must be of type {expected_type}.")
        return row["ledger_account_id"]

    def _refundable_original(self, transaction_id: str, amount_minor: int) -> sqlite3.Row:
        original = self.conn.execute(
            "SELECT t.id, t.counterparty_account_id, t.category_id, t.user_share_minor, t.review_status, "
            "t.transaction_type, e.entry_type, a.account_class AS counterparty_class "
            "FROM transactions t JOIN journal_entries e ON e.id = t.journal_entry_id "
            "JOIN accounts a ON a.id = t.counterparty_account_id WHERE t.id = ?",
            (transaction_id,),
        ).fetchone()
        if original is None:
            raise ValueError("Unknown original transaction.")
        if (
            original["entry_type"] not in _EXPENSE_ENTRY_TYPES
            or original["transaction_type"] != "EXPENSE"
            or original["counterparty_class"] != "EXPENSE"
            or original["review_status"] == "SUPERSEDED"
        ):
            raise ValueError("Original transaction is not a refundable expense.")
        refunded = self.conn.execute(
            "SELECT COALESCE(SUM(t.amount_minor), 0) AS s FROM transactions t "
            "JOIN journal_entries e ON e.id = t.journal_entry_id "
            "WHERE t.linked_transaction_id = ? AND e.entry_type = 'REFUND' "
            "AND t.review_status != 'SUPERSEDED'",
            (transaction_id,),
        ).fetchone()["s"]
        if amount_minor > original["user_share_minor"] - refunded:
            raise ValueError("Refund exceeds the refundable amount of the original transaction.")
        return original

    def _settleable_split(self, split_id: str, amount_minor: int) -> sqlite3.Row:
        split = self.conn.execute("SELECT * FROM reimbursable_splits WHERE id = ?", (split_id,)).fetchone()
        if split is None:
            raise ValueError("Unknown split.")
        if split["status"] not in ("OPEN", "PARTIAL"):
            raise ValueError("Split is not open for settlement.")
        if amount_minor > split["owed_amount_minor"] - split["settled_amount_minor"]:
            raise ValueError("Settlement exceeds the outstanding split amount.")
        return split

    # --------------------------------------------------------- side effects

    def _insert_splits(self, tx_id: str, specs: tuple[SplitShareSpec, ...]) -> None:
        for spec in specs:
            self.conn.execute(
                "INSERT INTO reimbursable_splits (id, transaction_id, counterparty_name, counterparty_vpa, "
                "owed_amount_minor, status) VALUES (?, ?, ?, ?, ?, 'OPEN')",
                (
                    str(uuid.uuid4()),
                    tx_id,
                    spec.counterparty_name,
                    spec.counterparty_vpa,
                    spec.owed_amount_minor,
                ),
            )

    def _apply_settlement(self, split: sqlite3.Row, amount_minor: int, tx_id: str) -> None:
        settled = split["settled_amount_minor"] + amount_minor
        status = "SETTLED" if settled == split["owed_amount_minor"] else "PARTIAL"
        self.conn.execute(
            "UPDATE reimbursable_splits SET settled_amount_minor = ?, status = ?, "
            "settlement_transaction_id = ? WHERE id = ?",
            (settled, status, tx_id, split["id"]),
        )

    # ---------------------------------------------------------------- reversal

    def _build_reversal(self, journal_entry_id: str, entry_date: date, idempotency_key: str) -> PostingPlan:
        original = self._reversible_entry(journal_entry_id)
        rows = self.conn.execute(
            "SELECT l.account_id, l.signed_amount_minor, l.memo, a.account_class FROM journal_lines l "
            "JOIN accounts a ON a.id = l.account_id WHERE l.journal_entry_id = ? ORDER BY l.rowid",
            (journal_entry_id,),
        ).fetchall()
        # Recategorization moved the user share to the transaction's current category ledger account;
        # the reversal must credit that account, not the one the entry was first posted to.
        current_ledger = original["counterparty_account_id"]
        lines = tuple(
            LineSpec(
                current_ledger if r["account_class"] in ("EXPENSE", "INCOME") else r["account_id"],
                -r["signed_amount_minor"],
                r["memo"],
            )
            for r in rows
        )
        flipped = "CREDIT" if original["direction"] == "DEBIT" else "DEBIT"
        return PostingPlan(
            entry_type="REVERSAL",
            entry_date=entry_date,
            idempotency_key=idempotency_key,
            lines=lines,
            tx=TxSpec(
                original["account_id"],
                original["counterparty_account_id"],
                original["amount_minor"],
                original["user_share_minor"],
                flipped,
                original["transaction_type"],
                category_id=original["category_id"],
                review_status="SUPERSEDED",
            ),  # fmt: skip
            meta=EntryMeta(),
            default_description=f"Reversal: {original['description']}",
            reverses_journal_entry_id=journal_entry_id,
            after=lambda _tx_id: self._supersede(original["id"]),
        )

    def _reversible_entry(self, journal_entry_id: str) -> sqlite3.Row:
        original = self.conn.execute(
            "SELECT t.*, e.entry_type, e.status FROM journal_entries e "
            "JOIN transactions t ON t.journal_entry_id = e.id WHERE e.id = ?",
            (journal_entry_id,),
        ).fetchone()
        if original is None or original["status"] != "POSTED":
            raise ValueError("Unknown or unposted journal entry.")
        if original["entry_type"] in ("REVERSAL", "REIMBURSEMENT_SETTLEMENT"):
            raise ValueError("This entry type cannot be reversed.")
        if self._exists(
            "SELECT 1 FROM journal_entries WHERE reverses_journal_entry_id = ?", journal_entry_id
        ):
            raise ValueError("Entry has already been reversed.")
        if self._exists(
            "SELECT 1 FROM transactions t JOIN journal_entries e ON e.id = t.journal_entry_id "
            "WHERE t.linked_transaction_id = ? AND e.entry_type = 'REFUND' "
            "AND t.review_status != 'SUPERSEDED'",
            original["id"],
        ):
            raise ValueError("Reverse the refunds of this transaction first.")
        if self._exists(
            "SELECT 1 FROM reimbursable_splits WHERE transaction_id = ? AND settled_amount_minor > 0",
            original["id"],
        ):
            raise ValueError("Entry has settled reimbursable splits and cannot be reversed.")
        return original

    def _exists(self, sql: str, param: str) -> bool:
        return self.conn.execute(sql, (param,)).fetchone() is not None

    def _supersede(self, transaction_id: str) -> None:
        self.conn.execute(
            "UPDATE transactions SET review_status = 'SUPERSEDED', "
            "updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
            (transaction_id,),
        )
        self.conn.execute(
            "UPDATE reimbursable_splits SET status = 'WRITTEN_OFF' WHERE transaction_id = ?",
            (transaction_id,),
        )
