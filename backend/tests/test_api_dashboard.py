from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.api_helpers import API, ApiEnv, build_env, key

# Fake clock "today" is 2026-11-12 (19 days left in November, today included).
TODAY = "2026-11-12"


@pytest.fixture
def env(tmp_path: Path) -> Iterator[ApiEnv]:
    built = build_env(tmp_path)
    yield built
    built.assert_ledger_clean()


def summary(env: ApiEnv) -> dict:
    response = env.client.get(f"{API}/dashboard/summary")
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_empty_dashboard(env: ApiEnv) -> None:
    data = summary(env)
    assert data["net_worth_minor"] == data["month_expense_minor"] == data["month_income_minor"] == 0
    assert data["upcoming_bills"] == []
    assert data["pending_review_count"] == 0
    block = data["safe_to_spend"]
    assert block["safe_to_spend_minor"] == 0
    assert block["days_remaining_in_month"] == 19
    assert data["month"] == "2026-11"


def transfer(env: ApiEnv, source: str, target: str, amount: int, day: str) -> dict:
    body = {
        "kind": "transfer",
        "from_account_id": source,
        "to_account_id": target,
        "amount_minor": amount,
        "transaction_date": day,
    }
    return env.transaction(body)


def build_known_ledger(env: ApiEnv) -> dict[str, str]:
    ids = {
        "bank": env.account("HDFC", opening_balance_minor=1_000_000, opening_date="2026-10-20"),
        "cash": env.account("Wallet", "WALLET"),
        "card": env.account("Card", "CREDIT_CARD"),
        "dining": env.category("Dining"),
        "salary": env.category("Salary", "INCOME"),
    }
    env.transaction({"kind": "income", "account_id": ids["bank"], "category_id": ids["salary"],
                     "amount_minor": 500_000, "transaction_date": "2026-11-05"})  # fmt: skip
    env.expense(ids["card"], ids["dining"], 200_000, "2026-11-06")  # card purchase
    env.expense(ids["bank"], ids["dining"], 30_000, "2026-11-08")
    transfer(env, ids["bank"], ids["card"], 150_000, "2026-11-10")  # card bill payment
    transfer(env, ids["bank"], ids["cash"], 100_000, "2026-11-11")  # own-account transfer
    env.expense(ids["bank"], ids["dining"], 999_00, "2026-10-15")  # last month: excluded from month totals
    return ids


def add_obligations(env: ApiEnv, ids: dict[str, str]) -> None:
    with env.db() as conn:
        conn.execute("INSERT INTO merchants (id, canonical_name) VALUES ('m1', 'Landlord')")
        conn.execute("INSERT INTO merchants (id, canonical_name) VALUES ('m2', 'Netflix')")
        rule = (
            "INSERT INTO recurring_rules (id, merchant_id, category_id, expected_amount_minor, "
            "moving_avg_amount_minor, frequency, next_expected_date, is_mandatory, is_active) "
            "VALUES (?, ?, ?, ?, ?, 'MONTHLY', ?, ?, ?)"
        )
        for rule_id, merchant, amount, due, mandatory, active in (
            ("r1", "m1", 20_000, "2026-11-20", 1, 1),  # in 30d, not in 7d
            ("r2", "m1", 5_000, "2026-11-15", 1, 1),  # in both
            ("r3", "m2", 7_000, "2026-11-14", 0, 1),  # optional: listed, not an obligation
            ("r4", "m1", 11_111, "2026-12-20", 1, 1),  # beyond 30 days
            ("r5", "m1", 22_222, "2026-11-16", 1, 0),  # inactive
        ):
            conn.execute(rule, (rule_id, merchant, ids["dining"], amount, amount, due, mandatory, active))
        goal = (
            "INSERT INTO financial_goals (id, name, target_amount_minor, current_locked_amount_minor, "
            "status) VALUES (?, ?, 9999999, ?, ?)"
        )
        conn.execute(goal, ("g1", "Trip", 100_000, "ACTIVE"))
        conn.execute(goal, ("g2", "Paused", 999, "PAUSED"))


def test_dashboard_numbers_for_a_known_ledger(env: ApiEnv) -> None:
    ids = build_known_ledger(env)
    add_obligations(env, ids)
    tx_id = env.client.get(f"{API}/transactions", params={"q": "Expense", "limit": 1}).json()["data"][0]["id"]
    env.sql("UPDATE transactions SET review_status = 'PENDING_REVIEW' WHERE id = ?", (tx_id,))

    data = summary(env)
    # bank 1,000,000 + 500,000 - 30,000 - 150,000 - 100,000 - 99,900 = 1,120,100; wallet 100,000; card -50,000
    liquid, card_owed = 1_120_100 + 100_000, 50_000
    assert data["month_expense_minor"] == 230_000  # card purchase + bank expense only
    assert data["month_income_minor"] == 500_000
    assert data["net_worth_minor"] == liquid - card_owed
    block = data["safe_to_spend"]
    assert block["liquid_cash_minor"] == liquid
    assert block["card_liability_minor"] == card_owed
    assert block["upcoming_obligations_minor"] == 25_000
    assert block["goal_locks_minor"] == 100_000
    expected = liquid - card_owed - 25_000 - 100_000
    assert block["safe_to_spend_minor"] == expected
    assert block["days_remaining_in_month"] == 19
    assert block["daily_safe_burn_minor"] == expected // 19
    assert block["is_liquidity_deficit"] is False
    assert [(b["id"], b["expected_amount_minor"], b["merchant_name"]) for b in data["upcoming_bills"]] == [
        ("r3", 7_000, "Netflix"),
        ("r2", 5_000, "Landlord"),
    ]
    assert data["pending_review_count"] == 1
    assert all(isinstance(v, int) for k, v in data.items() if k.endswith("_minor"))


def test_card_payment_and_transfer_do_not_move_month_totals(env: ApiEnv) -> None:
    ids = build_known_ledger(env)
    before = summary(env)
    transfer(env, ids["bank"], ids["card"], 50_000, TODAY)
    transfer(env, ids["cash"], ids["bank"], 10_000, TODAY)
    after = summary(env)
    assert after["month_expense_minor"] == before["month_expense_minor"]
    assert after["month_income_minor"] == before["month_income_minor"]
    assert after["net_worth_minor"] == before["net_worth_minor"]  # internal moves are net-worth neutral
    assert after["safe_to_spend"]["card_liability_minor"] == 0


def test_refund_reduces_month_expense_and_reversal_restores_it(env: ApiEnv) -> None:
    ids = build_known_ledger(env)
    spent = env.expense(ids["bank"], ids["dining"], 10_000, "2026-11-09")
    assert summary(env)["month_expense_minor"] == 240_000
    refund = env.transaction(
        {
            "kind": "refund",
            "account_id": ids["bank"],
            "original_transaction_id": spent["id"],
            "amount_minor": 4_000,
            "transaction_date": "2026-11-11",
        }
    )
    assert summary(env)["month_expense_minor"] == 236_000
    reversed_refund = env.client.post(f"{API}/transactions/{refund['id']}/reverse", headers=key())
    assert reversed_refund.status_code == 201
    assert summary(env)["month_expense_minor"] == 240_000


def test_recategorize_keeps_month_expense_total(env: ApiEnv) -> None:
    ids = build_known_ledger(env)
    other = env.category("Travel")
    tx = env.expense(ids["bank"], ids["dining"], 10_000, "2026-11-09")
    before = summary(env)["month_expense_minor"]
    response = env.client.patch(
        f"{API}/transactions/{tx['id']}", json={"category_id": other}, headers={"If-Match": "1"}
    )
    assert response.status_code == 200
    assert summary(env)["month_expense_minor"] == before


def test_liquidity_deficit_when_card_debt_exceeds_cash(env: ApiEnv) -> None:
    card = env.account("Card", "CREDIT_CARD")
    bank = env.account("Bank", opening_balance_minor=10_000, opening_date="2026-11-01")
    dining = env.category("Dining")
    env.expense(card, dining, 60_000, "2026-11-10")
    block = summary(env)["safe_to_spend"]
    assert block["safe_to_spend_minor"] == 0
    assert block["is_liquidity_deficit"] is True
    assert block["deficit_minor"] == 50_000
    assert bank
