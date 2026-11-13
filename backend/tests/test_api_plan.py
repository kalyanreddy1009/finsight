from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from app.finance.plan_queries import next_occurrence
from tests.api_helpers import API, IST, ORIGIN, PASSWORD, ApiEnv, build_env, key

# Fake clock "today" is 2026-11-12.
MONTH = "2026-11"


@pytest.fixture
def env(tmp_path: Path) -> Iterator[ApiEnv]:
    built = build_env(tmp_path)
    yield built
    built.assert_ledger_clean()


def summary(env: ApiEnv) -> dict[str, Any]:
    response = env.client.get(f"{API}/dashboard/summary")
    assert response.status_code == 200, response.text
    return response.json()["data"]


def bank(env: ApiEnv) -> str:
    return env.account("Bank", opening_balance_minor=10_000_000, opening_date="2026-01-01")


def put_budget(env: ApiEnv, body: dict[str, Any], month: str = MONTH) -> Any:
    return env.client.put(f"{API}/budgets/{month}", json=body)


def get_budget(env: ApiEnv, month: str = MONTH) -> dict[str, Any] | None:
    response = env.client.get(f"{API}/budgets/{month}")
    assert response.status_code == 200, response.text
    return response.json()["data"]["budget"]


def category_row(budget: dict[str, Any], name: str) -> dict[str, Any]:
    return next(c for c in budget["categories"] if c["category_name"] == name)


def tag_tax(env: ApiEnv, transaction_id: str, section: str) -> None:
    response = env.client.patch(
        f"{API}/transactions/{transaction_id}", json={"tax_section": section}, headers={"If-Match": "1"}
    )
    assert response.status_code == 200, response.text


def reverse(env: ApiEnv, transaction_id: str) -> None:
    response = env.client.post(f"{API}/transactions/{transaction_id}/reverse", headers=key())
    assert response.status_code == 201, response.text


def refund(env: ApiEnv, account_id: str, original_id: str, amount: int, day: str) -> dict[str, Any]:
    body = {
        "kind": "refund",
        "account_id": account_id,
        "original_transaction_id": original_id,
        "amount_minor": amount,
        "transaction_date": day,
    }
    return env.transaction(body)


def create_rule(env: ApiEnv, category_id: str, **overrides: Any) -> dict[str, Any]:
    body = {
        "merchant_name": "Landlord",
        "category_id": category_id,
        "expected_amount_minor": 20_000,
        "frequency": "MONTHLY",
        "next_expected_date": "2026-11-15",
        **overrides,
    }
    return env.post("/recurring", body)["data"]


def create_goal(env: ApiEnv, **overrides: Any) -> dict[str, Any]:
    body = {"name": "Trip", "target_amount_minor": 500_000, **overrides}
    return env.post("/goals", body)["data"]


# ------------------------------------------------------------------ auth


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/budgets/2026-11"),
        ("put", "/budgets/2026-11"),
        ("delete", "/budgets/2026-11"),
        ("get", "/goals"),
        ("post", "/goals"),
        ("patch", "/goals/g1"),
        ("delete", "/goals/g1"),
        ("get", "/recurring"),
        ("post", "/recurring"),
        ("patch", "/recurring/r1"),
        ("post", "/recurring/r1/advance"),
        ("delete", "/recurring/r1"),
        ("get", "/tax/summary"),
    ],
)
def test_plan_routes_reject_anonymous_requests(env: ApiEnv, method: str, path: str) -> None:
    response = env.anon.request(method.upper(), f"{API}{path}", json={})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize(("method", "path"), [("PUT", "/budgets/2026-11"), ("DELETE", "/recurring/r1")])
def test_cors_preflight_allows_put_and_delete_from_configured_origin(
    env: ApiEnv, method: str, path: str
) -> None:
    headers = {
        "Origin": ORIGIN,
        "Access-Control-Request-Method": method,
        "Access-Control-Request-Headers": "authorization,content-type",
    }
    response = env.anon.options(f"{API}{path}", headers=headers)
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert method in response.headers["access-control-allow-methods"].split(", ")


# --------------------------------------------------------------- budgets


def test_get_budget_returns_null_when_month_has_no_budget(env: ApiEnv) -> None:
    response = env.client.get(f"{API}/budgets/{MONTH}")
    assert response.status_code == 200
    assert response.json()["data"] == {"month": MONTH, "budget": None}


def test_put_budget_creates_budget_with_categories_ordered_by_name(env: ApiEnv) -> None:
    dining = env.category("Dining")
    groceries = env.category("Groceries")
    body = {
        "name": "November",
        "total_limit_minor": 100_000,
        "categories": [
            {"category_id": dining, "limit_minor": 60_000, "alert_threshold_pct": 75},
            {"category_id": groceries, "limit_minor": 30_000},
        ],
    }
    response = put_budget(env, body)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["month"] == MONTH
    budget = response.json()["data"]["budget"]
    assert budget["name"] == "November"
    assert budget["period_month"] == MONTH
    assert budget["total_limit_minor"] == 100_000
    assert budget["spent_minor"] == 0
    assert [c["category_name"] for c in budget["categories"]] == ["Dining", "Groceries"]
    assert category_row(budget, "Dining") == {
        "category_id": dining,
        "category_name": "Dining",
        "limit_minor": 60_000,
        "alert_threshold_pct": 75,
        "spent_minor": 0,
    }
    assert category_row(budget, "Groceries")["alert_threshold_pct"] == 80
    assert get_budget(env, MONTH) == budget


def test_put_budget_replaces_existing_month_and_keeps_one_row(env: ApiEnv) -> None:
    dining = env.category("Dining")
    groceries = env.category("Groceries")
    put_budget(env, {"total_limit_minor": 100_000, "categories": [{"category_id": dining, "limit_minor": 5}]})
    replacement = {"total_limit_minor": 90_000, "categories": [{"category_id": groceries, "limit_minor": 7}]}
    put_budget(env, replacement)
    budget = get_budget(env)
    assert budget is not None
    assert budget["name"] == "Monthly Budget"
    assert budget["total_limit_minor"] == 90_000
    assert [c["category_name"] for c in budget["categories"]] == ["Groceries"]
    assert env.sql("SELECT COUNT(*) AS n FROM budgets")[0]["n"] == 1
    assert env.sql("SELECT COUNT(*) AS n FROM budget_categories")[0]["n"] == 1


def test_budget_spent_nets_expense_refund_and_reversal(env: ApiEnv) -> None:
    account = bank(env)
    dining = env.category("Dining")
    travel = env.category("Travel")
    put_budget(
        env,
        {"total_limit_minor": 100_000, "categories": [{"category_id": dining, "limit_minor": 50_000}]},
    )
    kept = env.expense(account, dining, 20_000, "2026-11-03")
    reversed_expense = env.expense(account, dining, 10_000, "2026-11-04")
    refund(env, account, kept["id"], 5_000, "2026-11-06")
    reverse(env, reversed_expense["id"])
    env.expense(account, travel, 7_000, "2026-11-07")  # not in the budget, still month expense

    budget = get_budget(env)
    assert budget is not None
    assert category_row(budget, "Dining")["spent_minor"] == 15_000  # 20,000 - 5,000 refund; reversal nets out
    assert budget["spent_minor"] == 22_000  # whole month expense flow, including unbudgeted Travel


def test_budget_spent_excludes_last_day_of_previous_month_and_first_day_of_next(env: ApiEnv) -> None:
    account = bank(env)
    dining = env.category("Dining")
    put_budget(
        env, {"total_limit_minor": 100_000, "categories": [{"category_id": dining, "limit_minor": 50_000}]}
    )
    env.expense(account, dining, 1_000, "2026-10-31")
    env.expense(account, dining, 2_000, "2026-11-01")
    env.expense(account, dining, 4_000, "2026-11-30")
    env.expense(account, dining, 8_000, "2026-12-01")

    budget = get_budget(env)
    assert budget is not None
    assert category_row(budget, "Dining")["spent_minor"] == 6_000
    assert budget["spent_minor"] == 6_000


def test_put_budget_rejects_unknown_and_non_expense_categories(env: ApiEnv) -> None:
    salary = env.category("Salary", "INCOME")
    for category_id in (salary, "no-such-category"):
        category = {"category_id": category_id, "limit_minor": 1_000}
        body = {"total_limit_minor": 5_000, "categories": [category]}
        response = put_budget(env, body)
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert get_budget(env) is None


def test_put_budget_rejects_repeated_category(env: ApiEnv) -> None:
    dining = env.category("Dining")
    body = {
        "total_limit_minor": 5_000,
        "categories": [
            {"category_id": dining, "limit_minor": 1_000},
            {"category_id": dining, "limit_minor": 2_000},
        ],
    }
    response = put_budget(env, body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_put_budget_rejects_category_limits_above_total(env: ApiEnv) -> None:
    dining = env.category("Dining")
    groceries = env.category("Groceries")
    body = {
        "total_limit_minor": 5_000,
        "categories": [
            {"category_id": dining, "limit_minor": 3_000},
            {"category_id": groceries, "limit_minor": 2_001},
        ],
    }
    response = put_budget(env, body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def _single_category(**fields: Any) -> dict[str, Any]:
    return {"total_limit_minor": 100, "categories": [{"category_id": "x", "limit_minor": 10, **fields}]}


TOO_MANY_CATEGORIES = [{"category_id": f"c{i}", "limit_minor": 1} for i in range(51)]


@pytest.mark.parametrize(
    "body",
    [
        {"total_limit_minor": 0},
        {"total_limit_minor": 1.5},
        {"name": "", "total_limit_minor": 100},
        {"name": "x" * 101, "total_limit_minor": 100},
        {"total_limit_minor": 100, "categories": [{"category_id": "x", "limit_minor": 0}]},
        _single_category(alert_threshold_pct=0),
        _single_category(alert_threshold_pct=101),
        {"total_limit_minor": 100, "categories": TOO_MANY_CATEGORIES},
    ],
)
def test_put_budget_rejects_invalid_body(env: ApiEnv, body: dict[str, Any]) -> None:
    response = put_budget(env, body)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("month", ["2026-13", "2026-00", "2026-11-01", "26-11", "2026-1"])
def test_budget_routes_reject_malformed_month(env: ApiEnv, month: str) -> None:
    assert env.client.get(f"{API}/budgets/{month}").status_code == 422
    assert env.client.delete(f"{API}/budgets/{month}").status_code == 422


def test_delete_budget_removes_it_then_reports_not_found(env: ApiEnv) -> None:
    dining = env.category("Dining")
    budget = {"total_limit_minor": 5_000, "categories": [{"category_id": dining, "limit_minor": 1_000}]}
    put_budget(env, budget)
    response = env.client.delete(f"{API}/budgets/{MONTH}")
    assert response.status_code == 200
    assert response.json()["data"] == {"deleted": True}
    assert get_budget(env) is None
    missing = env.client.delete(f"{API}/budgets/{MONTH}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    assert env.sql("SELECT COUNT(*) AS n FROM budget_categories")[0]["n"] == 0


# ----------------------------------------------------------------- goals


def test_create_goal_starts_active_with_defaults(env: ApiEnv) -> None:
    response = env.post("/goals", {"name": "Trip", "target_amount_minor": 500_000})
    goal = response["data"]
    assert goal["name"] == "Trip"
    assert goal["status"] == "ACTIVE"
    assert goal["current_locked_amount_minor"] == 0
    assert goal["monthly_contribution_minor"] == 0
    assert goal["priority"] == 1
    assert goal["target_date"] is None
    assert goal["linked_account_id"] is None
    assert set(goal) == {
        "id", "name", "linked_account_id", "target_amount_minor", "current_locked_amount_minor",
        "monthly_contribution_minor", "target_date", "priority", "status", "created_at",
    }  # fmt: skip


def test_list_goals_orders_by_priority_then_creation(env: ApiEnv) -> None:
    low = create_goal(env, name="Later", priority=5)
    first = create_goal(env, name="Emergency", priority=1)
    second = create_goal(env, name="Car", priority=1)
    response = env.client.get(f"{API}/goals")
    assert response.status_code == 200
    rows = response.json()["data"]
    assert [g["priority"] for g in rows] == [1, 1, 5]
    assert {rows[0]["id"], rows[1]["id"]} == {first["id"], second["id"]}
    assert rows[2]["id"] == low["id"]


def test_create_goal_with_locked_amount_and_linked_account(env: ApiEnv) -> None:
    account = bank(env)
    goal = create_goal(
        env,
        current_locked_amount_minor=100_000,
        monthly_contribution_minor=10_000,
        target_date="2027-06-30",
        priority=99,
        linked_account_id=account,
    )
    assert goal["current_locked_amount_minor"] == 100_000
    assert goal["target_date"] == "2027-06-30"
    assert goal["priority"] == 99
    assert goal["linked_account_id"] == account


@pytest.mark.parametrize(
    "body",
    [
        {"name": "Trip", "target_amount_minor": 0},
        {"name": "Trip", "target_amount_minor": 100.0},
        {"name": "Trip", "target_amount_minor": 100, "current_locked_amount_minor": -1},
        {"name": "Trip", "target_amount_minor": 100, "current_locked_amount_minor": 200},
        {"name": "Trip", "target_amount_minor": 100, "priority": 100},
        {"name": "Trip", "target_amount_minor": 100, "priority": 0},
        {"name": "", "target_amount_minor": 100},
        {"name": "Trip", "target_amount_minor": 100, "linked_account_id": "no-such-account"},
    ],
)
def test_create_goal_rejects_invalid_body(env: ApiEnv, body: dict[str, Any]) -> None:
    response = env.client.post(f"{API}/goals", json=body)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert env.client.get(f"{API}/goals").json()["data"] == []


def test_patch_goal_changes_only_given_fields_and_status(env: ApiEnv) -> None:
    goal = create_goal(env, monthly_contribution_minor=5_000, target_date="2027-01-01")
    response = env.client.patch(f"{API}/goals/{goal['id']}", json={"status": "PAUSED", "priority": 3})
    assert response.status_code == 200, response.text
    updated = response.json()["data"]
    assert updated["status"] == "PAUSED"
    assert updated["priority"] == 3
    assert updated["monthly_contribution_minor"] == 5_000
    assert updated["target_date"] == "2027-01-01"


def test_patch_goal_explicit_null_clears_target_date(env: ApiEnv) -> None:
    goal = create_goal(env, target_date="2027-01-01")
    response = env.client.patch(f"{API}/goals/{goal['id']}", json={"target_date": None})
    assert response.status_code == 200
    assert response.json()["data"]["target_date"] is None


def test_patch_goal_validates_the_resulting_row(env: ApiEnv) -> None:
    goal = create_goal(env, current_locked_amount_minor=80_000)
    response = env.client.patch(f"{API}/goals/{goal['id']}", json={"target_amount_minor": 50_000})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    unchanged = env.client.get(f"{API}/goals").json()["data"][0]
    assert unchanged["target_amount_minor"] == 500_000


@pytest.mark.parametrize(
    "body",
    [{}, {"name": None}, {"status": None}, {"target_amount_minor": 0}, {"status": "DONE"}],
)
def test_patch_goal_rejects_empty_or_invalid_changes(env: ApiEnv, body: dict[str, Any]) -> None:
    goal = create_goal(env)
    response = env.client.patch(f"{API}/goals/{goal['id']}", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_goal_routes_report_unknown_id_as_not_found(env: ApiEnv) -> None:
    patch = env.client.patch(f"{API}/goals/missing", json={"priority": 2})
    delete = env.client.delete(f"{API}/goals/missing")
    assert patch.status_code == 404
    assert patch.json()["error"]["code"] == "NOT_FOUND"
    assert delete.status_code == 404


def test_delete_goal_returns_deleted_flag(env: ApiEnv) -> None:
    goal = create_goal(env)
    response = env.client.delete(f"{API}/goals/{goal['id']}")
    assert response.status_code == 200
    assert response.json()["data"] == {"deleted": True}
    assert env.client.get(f"{API}/goals").json()["data"] == []


# -------------------------------------------------------------- recurring


def test_create_recurring_stores_average_and_due_day(env: ApiEnv) -> None:
    dining = env.category("Dining")
    account = bank(env)
    response = env.post(
        "/recurring",
        {
            "merchant_name": "Landlord",
            "category_id": dining,
            "account_id": account,
            "expected_amount_minor": 20_000,
            "frequency": "MONTHLY",
            "next_expected_date": "2026-11-15",
        },
    )
    rule = response["data"]
    assert rule["merchant_name"] == "Landlord"
    assert rule["category_name"] == "Dining"
    assert rule["account_id"] == account
    assert rule["expected_amount_minor"] == 20_000
    assert rule["is_mandatory"] is True
    assert rule["is_active"] is True
    assert rule["next_expected_date"] == "2026-11-15"
    stored = env.sql(
        "SELECT moving_avg_amount_minor, expected_day_of_month FROM recurring_rules WHERE id = ?",
        (rule["id"],),
    )
    assert (stored[0]["moving_avg_amount_minor"], stored[0]["expected_day_of_month"]) == (20_000, 15)


def test_create_recurring_reuses_merchant_regardless_of_case(env: ApiEnv) -> None:
    dining = env.category("Dining")
    first = create_rule(env, dining, merchant_name="Landlord")
    second = create_rule(env, dining, merchant_name="  landlord ", next_expected_date="2026-12-15")
    assert first["merchant_id"] == second["merchant_id"]
    assert second["merchant_name"] == "Landlord"
    count = env.sql("SELECT COUNT(*) AS n FROM merchants WHERE canonical_name = 'landlord' COLLATE NOCASE")
    assert count[0]["n"] == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"category_id": "no-such-category"},
        {"category_id": "INCOME"},
        {"account_id": "no-such-account"},
        {"merchant_name": "   "},
        {"expected_amount_minor": 0},
        {"frequency": "DAILY"},
        {"next_expected_date": "15/11/2026"},
    ],
)
def test_create_recurring_rejects_invalid_references_and_values(
    env: ApiEnv, overrides: dict[str, Any]
) -> None:
    dining = env.category("Dining")
    income = env.category("INCOME", "INCOME")
    body = {
        "merchant_name": "Landlord",
        "category_id": dining,
        "expected_amount_minor": 20_000,
        "frequency": "MONTHLY",
        "next_expected_date": "2026-11-15",
        **overrides,
    }
    if body["category_id"] == "INCOME":
        body["category_id"] = income
    response = env.client.post(f"{API}/recurring", json=body)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert env.client.get(f"{API}/recurring").json()["data"] == []


def test_list_recurring_includes_inactive_ordered_by_due_date(env: ApiEnv) -> None:
    dining = env.category("Dining")
    late = create_rule(env, dining, merchant_name="Gym", next_expected_date="2026-12-01")
    early = create_rule(env, dining, merchant_name="Netflix", next_expected_date="2026-11-02")
    env.client.patch(f"{API}/recurring/{early['id']}", json={"is_active": False, "is_mandatory": False})
    rows = env.client.get(f"{API}/recurring").json()["data"]
    assert [r["id"] for r in rows] == [early["id"], late["id"]]
    assert rows[0]["is_active"] is False
    assert rows[0]["is_mandatory"] is False
    assert rows[1]["is_active"] is True


def test_patch_recurring_updates_fields_and_resets_due_day(env: ApiEnv) -> None:
    dining = env.category("Dining")
    travel = env.category("Travel")
    rule = create_rule(env, dining)
    response = env.client.patch(
        f"{API}/recurring/{rule['id']}",
        json={
            "expected_amount_minor": 25_000,
            "frequency": "QUARTERLY",
            "next_expected_date": "2026-12-31",
            "category_id": travel,
        },
    )
    assert response.status_code == 200, response.text
    updated = response.json()["data"]
    assert updated["expected_amount_minor"] == 25_000
    assert updated["frequency"] == "QUARTERLY"
    assert updated["next_expected_date"] == "2026-12-31"
    assert updated["category_name"] == "Travel"
    day = env.sql("SELECT expected_day_of_month FROM recurring_rules WHERE id = ?", (rule["id"],))
    assert day[0]["expected_day_of_month"] == 31


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"is_active": None},
        {"expected_amount_minor": 0},
        {"category_id": "INCOME"},
        {"frequency": "DAILY"},
    ],
)
def test_patch_recurring_rejects_empty_null_or_invalid_changes(env: ApiEnv, body: dict[str, Any]) -> None:
    dining = env.category("Dining")
    income = env.category("Salary", "INCOME")
    rule = create_rule(env, dining)
    if body.get("category_id") == "INCOME":
        body = {"category_id": income}
    response = env.client.patch(f"{API}/recurring/{rule['id']}", json=body)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_advance_moves_month_end_bill_through_short_months(env: ApiEnv) -> None:
    dining = env.category("Dining")
    rule = create_rule(env, dining, next_expected_date="2027-01-31")
    dates = []
    for _ in range(3):
        response = env.client.post(f"{API}/recurring/{rule['id']}/advance")
        assert response.status_code == 200, response.text
        dates.append(response.json()["data"]["next_expected_date"])
    assert dates == ["2027-02-28", "2027-03-31", "2027-04-30"]


def test_patch_date_on_short_month_end_keeps_day_31_so_advance_does_not_drift(env: ApiEnv) -> None:
    dining = env.category("Dining")
    rule = create_rule(env, dining, next_expected_date="2026-12-31")
    response = env.client.patch(f"{API}/recurring/{rule['id']}", json={"next_expected_date": "2027-02-28"})
    assert response.status_code == 200, response.text
    stored = env.sql("SELECT expected_day_of_month FROM recurring_rules WHERE id = ?", (rule["id"],))
    assert stored[0]["expected_day_of_month"] == 31
    advanced = env.client.post(f"{API}/recurring/{rule['id']}/advance")
    assert advanced.json()["data"]["next_expected_date"] == "2027-03-31"


def test_patch_date_off_month_end_resets_day_to_new_date(env: ApiEnv) -> None:
    dining = env.category("Dining")
    rule = create_rule(env, dining, next_expected_date="2026-12-31")
    response = env.client.patch(f"{API}/recurring/{rule['id']}", json={"next_expected_date": "2027-03-15"})
    assert response.status_code == 200, response.text
    stored = env.sql("SELECT expected_day_of_month FROM recurring_rules WHERE id = ?", (rule["id"],))
    assert stored[0]["expected_day_of_month"] == 15


def test_advance_unknown_rule_reports_not_found(env: ApiEnv) -> None:
    response = env.client.post(f"{API}/recurring/missing/advance")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_delete_recurring_returns_deleted_flag_then_not_found(env: ApiEnv) -> None:
    dining = env.category("Dining")
    rule = create_rule(env, dining)
    response = env.client.delete(f"{API}/recurring/{rule['id']}")
    assert response.status_code == 200
    assert response.json()["data"] == {"deleted": True}
    assert env.client.delete(f"{API}/recurring/{rule['id']}").status_code == 404


# ----------------------------------------------------------- next_occurrence


@pytest.mark.parametrize(
    ("current", "frequency", "day", "expected"),
    [
        (date(2026, 11, 12), "WEEKLY", None, date(2026, 11, 19)),
        (date(2026, 12, 28), "WEEKLY", 28, date(2027, 1, 4)),
        (date(2026, 12, 15), "MONTHLY", 15, date(2027, 1, 15)),
        (date(2027, 1, 31), "MONTHLY", 31, date(2027, 2, 28)),
        (date(2027, 2, 28), "MONTHLY", 31, date(2027, 3, 31)),
        (date(2027, 1, 31), "MONTHLY", None, date(2027, 2, 28)),
        (date(2028, 1, 31), "MONTHLY", 31, date(2028, 2, 29)),
        (date(2026, 11, 30), "QUARTERLY", 30, date(2027, 2, 28)),
        (date(2026, 10, 31), "QUARTERLY", 31, date(2027, 1, 31)),
        (date(2026, 4, 10), "YEARLY", 10, date(2027, 4, 10)),
        (date(2028, 2, 29), "YEARLY", 29, date(2029, 2, 28)),
        (date(2029, 2, 28), "YEARLY", 29, date(2030, 2, 28)),
    ],
)
def test_next_occurrence_handles_periods_and_clamping(
    current: date, frequency: str, day: int | None, expected: date
) -> None:
    assert next_occurrence(current, frequency, day) == expected


def test_next_occurrence_rejects_unknown_frequency() -> None:
    with pytest.raises(ValueError, match="Unknown frequency"):
        next_occurrence(date(2026, 1, 1), "DAILY", None)


# ---------------------------------------------------------------- tax


def test_tax_summary_applies_fy_boundaries_for_31_march_and_1_april(env: ApiEnv) -> None:
    account = bank(env)
    dining = env.category("Dining")
    dates_and_amounts = [
        ("2026-03-31", 9_000),  # FY 2025
        ("2026-04-01", 1_000),  # FY 2026
        ("2027-03-31", 2_000),  # FY 2026
        ("2027-04-01", 4_000),  # FY 2027
    ]
    for day, amount in dates_and_amounts:
        tag_tax(env, env.expense(account, dining, amount, day)["id"], "80C")

    fy_2026 = env.client.get(f"{API}/tax/summary", params={"fy": 2026}).json()["data"]
    assert fy_2026["start_date"] == "2026-04-01"
    assert fy_2026["end_date"] == "2027-03-31"
    assert fy_2026["sections"] == [
        {"tax_section": "80C", "total_minor": 3_000, "transaction_count": 2, "limit_minor": 15_000_000}
    ]
    assert fy_2026["total_minor"] == 3_000
    fy_2025 = env.client.get(f"{API}/tax/summary", params={"fy": 2025}).json()["data"]
    assert fy_2025["sections"][0]["total_minor"] == 9_000


def test_tax_summary_excludes_reversed_transactions_and_their_reversals(env: ApiEnv) -> None:
    account = bank(env)
    dining = env.category("Dining")
    reversed_tx = env.expense(account, dining, 10_000, "2026-06-10")
    tag_tax(env, reversed_tx["id"], "80D")
    reverse(env, reversed_tx["id"])
    kept = env.expense(account, dining, 5_000, "2026-06-11")
    tag_tax(env, kept["id"], "80D")

    data = env.client.get(f"{API}/tax/summary", params={"fy": 2026}).json()["data"]
    assert data["sections"] == [
        {"tax_section": "80D", "total_minor": 5_000, "transaction_count": 1, "limit_minor": 2_500_000}
    ]
    assert data["total_minor"] == 5_000


def test_tax_summary_counts_only_tagged_expenses_and_investments(env: ApiEnv) -> None:
    account = bank(env)
    dining = env.category("Dining")
    salary = env.category("Salary", "INCOME")
    tag_tax(env, env.expense(account, dining, 3_000, "2026-07-01")["id"], "HRA")
    income = env.transaction(
        {"kind": "income", "account_id": account, "category_id": salary, "amount_minor": 50_000,
         "transaction_date": "2026-07-02"}
    )  # fmt: skip
    tag_tax(env, income["id"], "80C")
    env.expense(account, dining, 9_000, "2026-07-03")  # untagged

    data = env.client.get(f"{API}/tax/summary", params={"fy": 2026}).json()["data"]
    assert data["sections"] == [
        {"tax_section": "HRA", "total_minor": 3_000, "transaction_count": 1, "limit_minor": None}
    ]


def test_new_expense_takes_the_default_tax_section_of_its_category(env: ApiEnv) -> None:
    account = bank(env)
    insurance = env.post(
        "/categories", {"name": "Insurance", "category_type": "EXPENSE", "default_tax_section": "80D"}
    )["data"]["id"]
    bonus = env.post(
        "/categories", {"name": "Bonus", "category_type": "INCOME", "default_tax_section": "80C"}
    )["data"]["id"]

    expense = env.expense(account, insurance, 7_000, "2026-07-01")
    plain = env.expense(account, env.category("Dining"), 1_000, "2026-07-01")
    income = env.transaction(
        {"kind": "income", "account_id": account, "category_id": bonus, "amount_minor": 9_000,
         "transaction_date": "2026-07-02"}
    )  # fmt: skip

    assert expense["tax_section"] == "80D"
    assert plain["tax_section"] == "NONE"
    assert income["tax_section"] == "NONE"
    data = env.client.get(f"{API}/tax/summary", params={"fy": 2026}).json()["data"]
    assert data["sections"] == [
        {"tax_section": "80D", "total_minor": 7_000, "transaction_count": 1, "limit_minor": 2_500_000}
    ]


def relogin(env: ApiEnv) -> None:
    """Access tokens last 15 minutes, so a moved fake clock needs a fresh token."""
    response = env.anon.post(f"{API}/auth/login", json={"password": PASSWORD, "device_name": "Test browser"})
    assert response.status_code == 200, response.text
    env.client.headers["Authorization"] = f"Bearer {response.json()['data']['access_token']}"


def test_tax_summary_defaults_to_financial_year_of_the_clock(env: ApiEnv) -> None:
    env.clock.now = datetime(2027, 3, 31, 10, 0, tzinfo=IST)
    relogin(env)
    assert env.client.get(f"{API}/tax/summary").json()["data"]["fy"] == 2026
    env.clock.now = datetime(2027, 4, 1, 10, 0, tzinfo=IST)
    relogin(env)
    data = env.client.get(f"{API}/tax/summary").json()["data"]
    assert data["fy"] == 2027
    assert data["start_date"] == "2027-04-01"


def test_tax_summary_rejects_year_out_of_range(env: ApiEnv) -> None:
    assert env.client.get(f"{API}/tax/summary", params={"fy": 1999}).status_code == 422


# ----------------------------------------------------- dashboard interaction


def test_due_mandatory_bill_and_goal_lock_change_dashboard_figures(env: ApiEnv) -> None:
    bank(env)
    dining = env.category("Dining")
    before = summary(env)["safe_to_spend"]
    rule = create_rule(env, dining, expected_amount_minor=20_000, next_expected_date="2026-11-15")
    goal = create_goal(env, target_amount_minor=500_000)

    with_bill = summary(env)
    assert [b["id"] for b in with_bill["upcoming_bills"]] == [rule["id"]]
    obligations = before["upcoming_obligations_minor"] + 20_000
    assert with_bill["safe_to_spend"]["upcoming_obligations_minor"] == obligations
    assert with_bill["safe_to_spend"]["safe_to_spend_minor"] == before["safe_to_spend_minor"] - 20_000

    response = env.client.patch(f"{API}/goals/{goal['id']}", json={"current_locked_amount_minor": 75_000})
    assert response.status_code == 200, response.text
    with_lock = summary(env)["safe_to_spend"]
    assert with_lock["goal_locks_minor"] == 75_000
    assert with_lock["safe_to_spend_minor"] == with_bill["safe_to_spend"]["safe_to_spend_minor"] - 75_000
