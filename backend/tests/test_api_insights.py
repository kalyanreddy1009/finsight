from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.api_helpers import API, ApiEnv, build_env

# Fake clock "today" is 2026-11-12.


@pytest.fixture
def env(tmp_path: Path) -> Iterator[ApiEnv]:
    built = build_env(tmp_path)
    yield built
    built.assert_ledger_clean()


def insights(env: ApiEnv, months: int | None = None) -> dict[str, Any]:
    suffix = "" if months is None else f"?months={months}"
    response = env.client.get(f"{API}/insights/summary{suffix}")
    assert response.status_code == 200, response.text
    return response.json()["data"]


def kinds(data: dict[str, Any]) -> list[str]:
    return [h["kind"] for h in data["highlights"]]


def bank(env: ApiEnv) -> str:
    return env.account("Bank", opening_balance_minor=10_000_000, opening_date="2026-01-01")


def income(env: ApiEnv, account: str, amount: int, day: str) -> None:
    salary = env.category("Salary", "INCOME")
    env.transaction(
        {
            "kind": "income",
            "account_id": account,
            "category_id": salary,
            "amount_minor": amount,
            "transaction_date": day,
        }
    )


def seed_two_months(env: ApiEnv) -> dict[str, str]:
    account = bank(env)
    ids = {"bank": account, "rent": env.category("Rent"), "food": env.category("Food")}
    ids["fun"] = env.category("Fun")
    env.expense(account, ids["rent"], 2_000_000, "2026-10-01")
    env.expense(account, ids["food"], 100_000, "2026-10-10")
    env.expense(account, ids["rent"], 2_000_000, "2026-11-01")
    env.expense(account, ids["food"], 300_000, "2026-11-05")
    env.expense(account, ids["fun"], 20_000, "2026-11-10")
    income(env, account, 5_000_000, "2026-11-01")
    return ids


def test_requires_authentication(env: ApiEnv) -> None:
    assert env.anon.get(f"{API}/insights/summary").status_code == 401


@pytest.mark.parametrize("months", ["0", "13", "abc"])
def test_months_outside_range_is_a_validation_error(env: ApiEnv, months: str) -> None:
    response = env.client.get(f"{API}/insights/summary?months={months}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_empty_ledger_reports_no_data(env: ApiEnv) -> None:
    data = insights(env)
    assert data["as_of"] == "2026-11-12"
    assert data["month"] == "2026-11"
    assert data["expense_minor"] == data["income_minor"] == data["net_minor"] == 0
    assert data["categories"] == []
    assert len(data["trend"]) == 6
    assert kinds(data) == ["NO_DATA"]
    assert data["highlights"][0]["severity"] == "info"


def test_totals_categories_and_shares(env: ApiEnv) -> None:
    seed_two_months(env)
    data = insights(env)
    assert data["expense_minor"] == 2_320_000
    assert data["income_minor"] == 5_000_000
    assert data["net_minor"] == 2_680_000
    assert data["previous_expense_minor"] == 2_100_000
    rows = [(c["name"], c["spent_minor"], c["previous_minor"], c["share_bp"]) for c in data["categories"]]
    assert rows == [
        ("Rent", 2_000_000, 2_000_000, 8620),
        ("Food", 300_000, 100_000, 1293),
        ("Fun", 20_000, 0, 86),
    ]
    assert set(data["categories"][0]) == {"category_id", "name", "spent_minor", "previous_minor", "share_bp"}


def test_trend_is_oldest_first_and_zero_filled(env: ApiEnv) -> None:
    seed_two_months(env)
    trend = insights(env, months=3)["trend"]
    assert trend == [
        {"year_month": "2026-09", "income_minor": 0, "expense_minor": 0},
        {"year_month": "2026-10", "income_minor": 0, "expense_minor": 2_100_000},
        {"year_month": "2026-11", "income_minor": 5_000_000, "expense_minor": 2_320_000},
    ]
    assert len(insights(env, months=12)["trend"]) == 12
    single = insights(env, months=1)
    assert [t["year_month"] for t in single["trend"]] == ["2026-11"]
    assert single["previous_expense_minor"] == 2_100_000


def test_reversed_spending_is_not_counted(env: ApiEnv) -> None:
    account = bank(env)
    food = env.category("Food")
    original = env.expense(account, food, 500_000, "2026-11-03")
    response = env.client.post(
        f"{API}/transactions/{original['id']}/reverse", headers={"Idempotency-Key": "rev-1"}
    )
    assert response.status_code == 201, response.text
    assert insights(env)["expense_minor"] == 0


def test_highlights_category_up_top_category_budget_and_bill(env: ApiEnv) -> None:
    ids = seed_two_months(env)
    budget = {
        "total_limit_minor": 2_400_000,
        "categories": [{"category_id": ids["food"], "limit_minor": 250_000}],
    }
    assert env.client.put(f"{API}/budgets/2026-11", json=budget).status_code == 200
    env.post(
        "/recurring",
        {
            "merchant_name": "Landlord",
            "category_id": ids["rent"],
            "expected_amount_minor": 2_000_000,
            "frequency": "MONTHLY",
            "next_expected_date": "2026-11-15",
        },
    )
    data = insights(env)
    assert sorted(kinds(data)) == ["BILL_DUE", "BUDGET_NEAR", "BUDGET_OVER", "CATEGORY_UP", "TOP_CATEGORY"]
    by_kind = {h["kind"]: h for h in data["highlights"]}
    assert by_kind["TOP_CATEGORY"]["severity"] == "info"
    assert "Rent" in by_kind["TOP_CATEGORY"]["title"]
    assert "₹20,000.00" in by_kind["TOP_CATEGORY"]["detail"]
    assert "Food" in by_kind["CATEGORY_UP"]["title"]
    assert by_kind["CATEGORY_UP"]["severity"] == "warning"
    assert "Food" in by_kind["BUDGET_OVER"]["title"]
    assert "₹3,000.00" in by_kind["BUDGET_OVER"]["detail"]
    assert "in 3 days" in by_kind["BILL_DUE"]["title"]
    severities = [h["severity"] for h in data["highlights"]]
    assert severities == sorted(severities, key=lambda s: s != "warning")


def test_bill_due_ignores_far_and_inactive_bills(env: ApiEnv) -> None:
    ids = seed_two_months(env)
    base = {"category_id": ids["rent"], "expected_amount_minor": 10_000, "frequency": "MONTHLY"}
    env.post("/recurring", {**base, "merchant_name": "Far", "next_expected_date": "2026-11-25"})
    env.post("/recurring", {**base, "merchant_name": "Today", "next_expected_date": "2026-11-12"})
    paused = env.post("/recurring", {**base, "merchant_name": "Paused", "next_expected_date": "2026-11-14"})
    patched = env.client.patch(f"{API}/recurring/{paused['data']['id']}", json={"is_active": False})
    assert patched.status_code == 200, patched.text
    bills = [h for h in insights(env)["highlights"] if h["kind"] == "BILL_DUE"]
    assert [b["title"] for b in bills] == ["Today is due today"]


def test_spending_up_against_previous_month(env: ApiEnv) -> None:
    account = bank(env)
    food = env.category("Food")
    env.expense(account, food, 100_000, "2026-10-05")
    env.expense(account, food, 400_000, "2026-11-05")
    data = insights(env)
    assert "SPENDING_UP" in kinds(data)
    assert "SPENDING_DOWN" not in kinds(data)
    up = next(h for h in data["highlights"] if h["kind"] == "SPENDING_UP")
    assert up["severity"] == "warning"
    assert "₹3,000.00" in up["detail"]


def test_spending_down_against_previous_month(env: ApiEnv) -> None:
    account = bank(env)
    food = env.category("Food")
    env.expense(account, food, 1_000_000, "2026-10-05")
    env.expense(account, food, 100_000, "2026-11-05")
    data = insights(env)
    assert "SPENDING_DOWN" in kinds(data)
    assert "SPENDING_UP" not in kinds(data)
    assert next(h for h in data["highlights"] if h["kind"] == "SPENDING_DOWN")["severity"] == "info"


def test_small_changes_produce_no_change_highlights(env: ApiEnv) -> None:
    account = bank(env)
    food = env.category("Food")
    env.expense(account, food, 100_000, "2026-10-05")
    env.expense(account, food, 120_000, "2026-11-05")  # +20% and +Rs 200: below both thresholds
    assert kinds(insights(env)) == ["TOP_CATEGORY"]


def test_budget_near_highlights_are_capped_and_ranked_before_info(env: ApiEnv) -> None:
    account = bank(env)
    budget_categories = []
    for index in range(8):
        cat = env.category(f"Cat{index}")
        env.expense(account, cat, 95_000, "2026-11-02")
        budget_categories.append({"category_id": cat, "limit_minor": 100_000})
    body = {"total_limit_minor": 800_000, "categories": budget_categories}
    assert env.client.put(f"{API}/budgets/2026-11", json=body).status_code == 200
    data = insights(env)
    assert len(data["highlights"]) == 6
    assert set(kinds(data)) == {"BUDGET_NEAR"}


def test_budget_total_over(env: ApiEnv) -> None:
    account = bank(env)
    food = env.category("Food")
    env.expense(account, food, 600_000, "2026-11-02")
    assert env.client.put(f"{API}/budgets/2026-11", json={"total_limit_minor": 500_000}).status_code == 200
    over = [h for h in insights(env)["highlights"] if h["kind"] == "BUDGET_OVER"]
    assert len(over) == 1
    assert "₹6,000.00" in over[0]["detail"]
    assert "₹5,000.00" in over[0]["detail"]


def test_comparison_uses_the_same_days_of_last_month(env: ApiEnv) -> None:
    account = bank(env)
    food = env.category("Food")
    env.expense(account, food, 1_000_000, "2026-10-20")  # after the same-day cutoff (Oct 12)
    env.expense(account, food, 100_000, "2026-11-05")
    data = insights(env)
    assert data["previous_expense_minor"] == 1_000_000  # full previous month stays as reported
    assert data["categories"][0]["previous_minor"] == 1_000_000
    assert "previous_to_date_minor" not in data["categories"][0]
    assert "SPENDING_DOWN" not in kinds(data)


def test_category_up_compares_month_to_date(env: ApiEnv) -> None:
    account = bank(env)
    food = env.category("Food")
    env.expense(account, food, 100_000, "2026-10-05")
    env.expense(account, food, 900_000, "2026-10-25")  # outside the same-days window
    env.expense(account, food, 300_000, "2026-11-05")
    data = insights(env)
    assert data["categories"][0]["previous_minor"] == 1_000_000
    assert "CATEGORY_UP" in kinds(data)  # 300k against 100k over the same days
    assert "SPENDING_UP" in kinds(data)


def test_previous_cutoff_is_clamped_to_the_last_day_of_the_previous_month() -> None:
    from datetime import date

    from app.finance.insights import previous_cutoff

    assert previous_cutoff(date(2026, 11, 12)) == date(2026, 10, 13)
    assert previous_cutoff(date(2026, 3, 31)) == date(2026, 3, 1)  # February has 28 days
    assert previous_cutoff(date(2026, 1, 31)) == date(2026, 1, 1)  # December 1..31 inclusive
