import base64
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.api_helpers import API, ApiEnv, build_env, key

DAY = "2026-11-12"


@pytest.fixture
def env(tmp_path: Path) -> Iterator[ApiEnv]:
    built = build_env(tmp_path)
    yield built
    built.assert_ledger_clean()


@pytest.fixture
def world(env: ApiEnv) -> dict[str, str]:
    return {
        "bank": env.account("HDFC", opening_balance_minor=1_000_000, opening_date="2026-11-01"),
        "bank2": env.account("SBI", "BANK_CURRENT"),
        "card": env.account("Card", "CREDIT_CARD", credit_limit_minor=5_000_000),
        "dining": env.category("Dining"),
        "travel": env.category("Travel"),
        "salary": env.category("Salary", "INCOME"),
    }


def balance(env: ApiEnv, account_id: str) -> int:
    accounts = env.client.get(f"{API}/accounts").json()["data"]
    return next(a["current_balance_minor"] for a in accounts if a["id"] == account_id)


# ----------------------------------------------------- accounts / categories


def test_accounts_list_hides_system_accounts_and_secrets(env: ApiEnv, world: dict[str, str]) -> None:
    accounts = env.client.get(f"{API}/accounts").json()["data"]
    assert {a["name"] for a in accounts} == {"HDFC", "SBI", "Card"}
    assert all("encrypted_pdf_password" not in a for a in accounts)
    hdfc = next(a for a in accounts if a["name"] == "HDFC")
    assert hdfc["current_balance_minor"] == 1_000_000
    assert hdfc["opening_balance_minor"] == 1_000_000
    assert hdfc["is_liquid"] is True
    assert hdfc["account_class"] == "ASSET"


def test_credit_card_opening_balance_is_amount_owed(env: ApiEnv) -> None:
    created = env.post(
        "/accounts",
        {
            "name": "Card",
            "account_subtype": "CREDIT_CARD",
            "opening_balance_minor": 50_000,
            "opening_date": DAY,
        },
    )["data"]
    assert created["account_class"] == "LIABILITY"
    assert created["current_balance_minor"] == -50_000


@pytest.mark.parametrize(
    "body",
    [
        {"name": "", "account_subtype": "CASH"},
        {"name": "X", "account_subtype": "SYSTEM_CATEGORY"},
        {"name": "X", "account_subtype": "CASH", "account_class": "LIABILITY"},
        {"name": "X", "account_subtype": "CASH", "opening_balance_minor": 100},
        {"name": "X", "account_subtype": "CASH", "opening_balance_minor": 10.5, "opening_date": DAY},
        {"name": "X", "account_subtype": "CASH", "opening_balance_minor": "100", "opening_date": DAY},
        {"name": "X", "account_subtype": "CASH", "opening_balance_minor": 100, "opening_date": "12/11/2026"},
        {"name": "X", "account_subtype": "CASH", "surprise": 1},
    ],
)
def test_account_create_validation(env: ApiEnv, body: dict) -> None:
    response = env.client.post(f"{API}/accounts", json=body)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert env.client.get(f"{API}/accounts").json()["data"] == []


def test_categories_create_and_list(env: ApiEnv) -> None:
    created = env.post(
        "/categories", {"name": "Insurance", "category_type": "EXPENSE", "default_tax_section": "80D"}
    )["data"]
    assert created["default_tax_section"] == "80D"
    assert created["is_discretionary"] is True
    listed = env.client.get(f"{API}/categories").json()["data"]
    assert created["id"] in {c["id"] for c in listed}
    bad = env.client.post(f"{API}/categories", json={"name": "X", "category_type": "TRANSFER"})
    assert bad.status_code == 422
    bad_tax = env.client.post(
        f"{API}/categories", json={"name": "X", "category_type": "EXPENSE", "default_tax_section": "99Z"}
    )
    assert bad_tax.status_code == 422


# ------------------------------------------------------------ transactions


def test_create_each_transaction_kind(env: ApiEnv, world: dict[str, str]) -> None:
    expense = env.expense(world["bank"], world["dining"], 25_000, DAY, description="Dinner")
    assert expense["transaction_type"] == "EXPENSE"
    assert expense["amount_minor"] == expense["user_share_minor"] == 25_000
    assert expense["category_name"] == "Dining"
    assert expense["version"] == 1

    income = env.transaction(
        {"kind": "income", "account_id": world["bank"], "category_id": world["salary"],
         "amount_minor": 500_000, "transaction_date": DAY}
    )  # fmt: skip
    assert income["direction"] == "CREDIT"

    transfer = env.transaction(
        {"kind": "transfer", "from_account_id": world["bank"], "to_account_id": world["bank2"],
         "amount_minor": 100_000, "transaction_date": DAY}
    )  # fmt: skip
    assert transfer["transaction_type"] == "TRANSFER"

    refund = env.transaction(
        {"kind": "refund", "account_id": world["bank"], "original_transaction_id": expense["id"],
         "amount_minor": 5_000, "transaction_date": DAY}
    )  # fmt: skip
    assert refund["transaction_type"] == "REFUND"
    assert refund["linked_transaction_id"] == expense["id"]
    assert balance(env, world["bank"]) == 1_000_000 - 25_000 + 500_000 - 100_000 + 5_000
    assert balance(env, world["bank2"]) == 100_000


def test_expense_with_splits_and_provisional_flag(env: ApiEnv, world: dict[str, str]) -> None:
    tx = env.expense(
        world["bank"], world["dining"], 90_000, DAY,
        splits=[{"counterparty_name": "Asha", "owed_amount_minor": 30_000}],
        is_provisional=True,
    )  # fmt: skip
    assert tx["user_share_minor"] == 60_000
    assert tx["review_status"] == "PROVISIONAL"
    splits = env.client.get(f"{API}/splits").json()["data"]
    assert [(s["counterparty_name"], s["outstanding_minor"], s["status"]) for s in splits] == [
        ("Asha", 30_000, "OPEN")
    ]


@pytest.mark.parametrize("amount", [100.5, 100.0, "100", True, 0, -5])
def test_non_integer_or_non_positive_amount_is_rejected(
    env: ApiEnv, world: dict[str, str], amount: object
) -> None:
    body = {"kind": "expense", "account_id": world["bank"], "category_id": world["dining"],
            "amount_minor": amount, "transaction_date": DAY}  # fmt: skip
    response = env.client.post(f"{API}/transactions", json=body, headers=key())
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert env.sql("SELECT COUNT(*) FROM transactions")[0][0] == 1  # only the opening balance


def test_transaction_error_paths(env: ApiEnv, world: dict[str, str]) -> None:
    good = {"kind": "expense", "account_id": world["bank"], "category_id": world["dining"],
            "amount_minor": 100, "transaction_date": DAY}  # fmt: skip

    def attempt(body: dict, headers: dict | None = None) -> tuple[int, str]:
        response = env.client.post(
            f"{API}/transactions", json=body, headers=key() if headers is None else headers
        )
        return response.status_code, (response.json()["error"] or {}).get("code", "")

    assert attempt(good, {}) == (400, "MISSING_IDEMPOTENCY_KEY")
    assert attempt({**good, "kind": "gift"}) == (422, "VALIDATION_ERROR")
    assert attempt({**good, "transaction_date": "2026-13-45"}) == (422, "VALIDATION_ERROR")
    assert attempt({**good, "transaction_date": 20261112}) == (422, "VALIDATION_ERROR")
    assert attempt({**good, "account_id": "missing"}) == (404, "NOT_FOUND")
    assert attempt({**good, "category_id": world["salary"]}) == (422, "VALIDATION_ERROR")
    assert attempt({**good, "splits": [{"counterparty_name": "A", "owed_amount_minor": 101}]}) == (
        422,
        "VALIDATION_ERROR",
    )
    transfer = {"kind": "transfer", "from_account_id": world["bank"], "to_account_id": world["bank"],
                "amount_minor": 1, "transaction_date": DAY}  # fmt: skip
    assert attempt(transfer) == (422, "VALIDATION_ERROR")
    assert env.sql("SELECT COUNT(*) FROM transactions")[0][0] == 1


def test_idempotent_replay_returns_same_transaction_without_double_posting(
    env: ApiEnv, world: dict[str, str]
) -> None:
    body = {"kind": "expense", "account_id": world["bank"], "category_id": world["dining"],
            "amount_minor": 40_000, "transaction_date": DAY}  # fmt: skip
    headers = key()
    first = env.client.post(f"{API}/transactions", json=body, headers=headers).json()["data"]
    entries_before = env.sql("SELECT COUNT(*) FROM journal_entries")[0][0]
    balance_before = balance(env, world["bank"])
    replay = env.client.post(f"{API}/transactions", json=body, headers=headers).json()["data"]
    assert replay["id"] == first["id"]
    assert env.sql("SELECT COUNT(*) FROM journal_entries")[0][0] == entries_before
    assert balance(env, world["bank"]) == balance_before == 1_000_000 - 40_000


def test_get_transaction_and_404(env: ApiEnv, world: dict[str, str]) -> None:
    tx = env.expense(world["bank"], world["dining"], 100, DAY)
    assert env.client.get(f"{API}/transactions/{tx['id']}").json()["data"]["id"] == tx["id"]
    assert env.client.get(f"{API}/transactions/missing").status_code == 404


# --------------------------------------------------------------- listing


def seed_many(env: ApiEnv, world: dict[str, str]) -> list[str]:
    ids = []
    for index in range(9):
        day = f"2026-11-{10 + index // 3:02d}"  # three rows per date -> exercises the id tiebreak
        ids.append(
            env.expense(world["bank"], world["dining"], 1_000 + index, day, description=f"Meal {index}")["id"]
        )
    return ids


def test_pagination_walks_every_row_exactly_once_in_order(env: ApiEnv, world: dict[str, str]) -> None:
    created = set(seed_many(env, world))
    seen: list[dict] = []
    cursor = None
    pages = 0
    while True:
        params = {"limit": 4, **({"cursor": cursor} if cursor else {})}
        body = env.client.get(f"{API}/transactions", params=params).json()
        seen.extend(body["data"])
        pages += 1
        cursor = body["meta"]["next_cursor"]
        if cursor is None:
            break
    ids = [t["id"] for t in seen]
    assert len(ids) == len(set(ids)) == 10  # 9 expenses + the opening balance
    assert created <= set(ids)
    keys = [(t["transaction_date"], t["id"]) for t in seen]
    assert keys == sorted(keys, reverse=True)
    assert pages == 3


def test_exact_page_boundary_has_no_dangling_cursor(env: ApiEnv, world: dict[str, str]) -> None:
    seed_many(env, world)
    body = env.client.get(f"{API}/transactions", params={"limit": 10}).json()
    assert len(body["data"]) == 10
    assert body["meta"]["next_cursor"] is None


def test_filters(env: ApiEnv, world: dict[str, str]) -> None:
    env.expense(world["bank"], world["dining"], 100, "2026-10-30", description="Old lunch")
    env.expense(world["bank2"], world["travel"], 200, "2026-11-05", description="Cab 100% fun_ride")
    env.expense(world["bank"], world["travel"], 300, "2026-11-06", description="Cab home")

    def ids(**params: str) -> list[int]:
        rows = env.client.get(f"{API}/transactions", params=params).json()["data"]
        return sorted(r["amount_minor"] for r in rows if r["entry_type"] != "OPENING_BALANCE")

    assert ids(date_from="2026-11-01") == [200, 300]
    assert ids(date_to="2026-10-31") == [100]
    assert ids(account_id=world["bank2"]) == [200]
    assert ids(category_id=world["travel"]) == [200, 300]
    assert ids(q="cab") == [200, 300]
    assert ids(q="100%") == [200]  # % is escaped, not a wildcard
    assert ids(q="fun_ride") == [200]
    assert ids(q="fun_r_de") == []  # _ is escaped too
    assert ids(review_status="USER_APPROVED", tax_section="NONE") == [100, 200, 300]
    assert ids(tax_section="80C") == []


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 201}, {"limit": "x"}, {"cursor": "garbage"}, {"date_from": "yesterday"},
     {"tax_section": "99Z"}, {"review_status": "NOPE"}],
)  # fmt: skip
def test_list_query_validation(env: ApiEnv, params: dict) -> None:
    response = env.client.get(f"{API}/transactions", params=params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_sql_injection_in_q_is_inert(env: ApiEnv, world: dict[str, str]) -> None:
    env.expense(world["bank"], world["dining"], 100, DAY)
    response = env.client.get(f"{API}/transactions", params={"q": "x' OR '1'='1"})
    assert response.status_code == 200
    assert response.json()["data"] == []


# ----------------------------------------------------------------- PATCH


def patch(env: ApiEnv, tx_id: str, body: dict, version: str | None = "1"):
    headers = {"If-Match": version} if version is not None else {}
    return env.client.patch(f"{API}/transactions/{tx_id}", json=body, headers=headers)


def test_patch_notes_and_tax_section_bumps_version(env: ApiEnv, world: dict[str, str]) -> None:
    tx = env.expense(world["bank"], world["dining"], 100, DAY)
    response = patch(env, tx["id"], {"notes": "client lunch", "tax_section": "80D"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert (data["notes"], data["tax_section"], data["version"]) == ("client lunch", "80D", 2)
    cleared = patch(env, tx["id"], {"notes": None}, version='"2"').json()["data"]
    assert cleared["notes"] is None
    assert cleared["version"] == 3
    assert cleared["tax_section"] == "80D"


def test_patch_version_conflict_returns_current_record(env: ApiEnv, world: dict[str, str]) -> None:
    tx = env.expense(world["bank"], world["dining"], 100, DAY)
    assert patch(env, tx["id"], {"notes": "first"}).status_code == 200
    stale = patch(env, tx["id"], {"notes": "second"})
    assert stale.status_code == 409
    body = stale.json()
    assert body["error"]["code"] == "VERSION_CONFLICT"
    assert body["meta"]["current"]["notes"] == "first"
    assert body["meta"]["current"]["version"] == 2


def test_patch_error_paths(env: ApiEnv, world: dict[str, str]) -> None:
    tx = env.expense(world["bank"], world["dining"], 100, DAY)
    assert patch(env, tx["id"], {"notes": "x"}, version=None).status_code == 428
    assert patch(env, tx["id"], {"notes": "x"}, version="abc").status_code == 400
    assert patch(env, tx["id"], {}).status_code == 422
    assert patch(env, tx["id"], {"tax_section": "99Z"}).status_code == 422
    assert patch(env, tx["id"], {"tax_section": None}).status_code == 422
    assert patch(env, tx["id"], {"amount_minor": 5}).status_code == 422
    assert patch(env, "missing", {"notes": "x"}).status_code == 404
    unknown_cat = patch(env, tx["id"], {"category_id": "missing"})
    assert unknown_cat.status_code == 404
    wrong_type = patch(env, tx["id"], {"category_id": world["salary"]})
    assert wrong_type.status_code == 422
    assert env.client.get(f"{API}/transactions/{tx['id']}").json()["data"]["version"] == 1


def test_patch_category_posts_balanced_adjustment_without_new_transaction(
    env: ApiEnv, world: dict[str, str]
) -> None:
    tx = env.expense(world["bank"], world["dining"], 80_000, DAY)
    tx_count = env.sql("SELECT COUNT(*) FROM transactions")[0][0]
    response = patch(env, tx["id"], {"category_id": world["travel"]})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["category_id"] == world["travel"]
    assert data["category_name"] == "Travel"
    assert data["version"] == 2
    assert env.sql("SELECT COUNT(*) FROM transactions")[0][0] == tx_count
    totals = {
        r["name"]: r["current_balance_minor"]
        for r in env.sql(
            "SELECT a.name, a.current_balance_minor FROM accounts a "
            "WHERE a.account_subtype = 'SYSTEM_CATEGORY' AND a.name IN ('Dining', 'Travel')"
        )
    }
    assert totals == {"Dining": 0, "Travel": 80_000}
    same = patch(env, tx["id"], {"category_id": world["travel"]}, version="2")
    assert same.status_code == 200
    assert env.sql("SELECT COUNT(*) FROM journal_entries")[0][0] == 3  # opening, expense, adjustment


# ---------------------------------------------------------------- reverse


def test_reverse_is_idempotent_and_supersedes_original(env: ApiEnv, world: dict[str, str]) -> None:
    tx = env.expense(world["bank"], world["dining"], 70_000, DAY)
    headers = key()
    first = env.client.post(f"{API}/transactions/{tx['id']}/reverse", headers=headers)
    assert first.status_code == 201
    reversal = first.json()["data"]
    assert reversal["entry_type"] == "REVERSAL"
    again = env.client.post(f"{API}/transactions/{tx['id']}/reverse", headers=headers).json()["data"]
    assert again["id"] == reversal["id"]
    assert balance(env, world["bank"]) == 1_000_000
    original = env.client.get(f"{API}/transactions/{tx['id']}").json()["data"]
    assert original["review_status"] == "SUPERSEDED"
    twice = env.client.post(f"{API}/transactions/{tx['id']}/reverse", headers=key())
    assert twice.status_code == 422


def test_reverse_error_paths(env: ApiEnv) -> None:
    assert env.client.post(f"{API}/transactions/missing/reverse", headers=key()).status_code == 404
    assert env.client.post(f"{API}/transactions/missing/reverse").status_code == 400


# ------------------------------------------------------------------ splits


def test_settle_split_flow(env: ApiEnv, world: dict[str, str]) -> None:
    env.expense(
        world["bank"], world["dining"], 90_000, DAY,
        splits=[{"counterparty_name": "Asha", "owed_amount_minor": 30_000}],
    )  # fmt: skip
    split = env.client.get(f"{API}/splits", params={"status": "OPEN"}).json()["data"][0]
    path = f"{API}/splits/{split['id']}/settle"
    body = {"bank_account_id": world["bank"], "amount_minor": 10_000}
    headers = key()
    first = env.client.post(path, json=body, headers=headers)
    assert first.status_code == 201
    result = first.json()["data"]
    assert result["split"]["status"] == "PARTIAL"
    assert result["split"]["outstanding_minor"] == 20_000
    replay = env.client.post(path, json=body, headers=headers).json()["data"]
    assert replay["transaction"]["id"] == result["transaction"]["id"]
    assert replay["split"]["settled_amount_minor"] == 10_000

    done = env.client.post(path, json={**body, "amount_minor": 20_000}, headers=key()).json()["data"]
    assert done["split"]["status"] == "SETTLED"
    assert env.client.get(f"{API}/splits", params={"status": "OPEN"}).json()["data"] == []
    assert len(env.client.get(f"{API}/splits", params={"status": "SETTLED"}).json()["data"]) == 1


def test_settle_split_error_paths(env: ApiEnv, world: dict[str, str]) -> None:
    env.expense(
        world["bank"], world["dining"], 90_000, DAY,
        splits=[{"counterparty_name": "Asha", "owed_amount_minor": 30_000}],
    )  # fmt: skip
    split_id = env.client.get(f"{API}/splits").json()["data"][0]["id"]
    path = f"{API}/splits/{split_id}/settle"
    body = {"bank_account_id": world["bank"], "amount_minor": 30_001}
    assert env.client.post(path, json=body, headers=key()).status_code == 422
    assert env.client.post(path, json={**body, "amount_minor": 1.5}, headers=key()).status_code == 422
    assert env.client.post(path, json={**body, "amount_minor": 1}).status_code == 400
    assert env.client.post(f"{API}/splits/missing/settle", json=body, headers=key()).status_code == 404
    assert env.client.get(f"{API}/splits", params={"status": "BOGUS"}).status_code == 422


def test_all_endpoints_require_auth(env: ApiEnv) -> None:
    for method, path in [
        ("get", "/accounts"), ("post", "/accounts"), ("get", "/categories"), ("post", "/categories"),
        ("get", "/transactions"), ("post", "/transactions"), ("get", "/transactions/x"),
        ("patch", "/transactions/x"), ("post", "/transactions/x/reverse"), ("get", "/splits"),
        ("post", "/splits/x/settle"), ("get", "/dashboard/summary"), ("get", "/auth/devices"),
        ("post", "/auth/logout"), ("post", "/auth/device-revoke"),
    ]:  # fmt: skip
        response = getattr(env.anon, method)(f"{API}{path}")
        assert response.status_code == 401, (method, path)
        assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_recategorize_income_and_rejects_unsupported_transactions(env: ApiEnv, world: dict[str, str]) -> None:
    bonus = env.category("Bonus", "INCOME")
    income = env.transaction(
        {
            "kind": "income",
            "account_id": world["bank"],
            "category_id": world["salary"],
            "amount_minor": 50_000,
            "transaction_date": DAY,
        }
    )
    assert patch(env, income["id"], {"category_id": bonus}).status_code == 200
    totals = {
        r["name"]: r["current_balance_minor"]
        for r in env.sql("SELECT name, current_balance_minor FROM accounts WHERE name IN ('Salary', 'Bonus')")
    }
    assert totals == {"Salary": 0, "Bonus": -50_000}  # income ledgers run negative (credit)

    transfer = env.transaction(
        {
            "kind": "transfer",
            "from_account_id": world["bank"],
            "to_account_id": world["bank2"],
            "amount_minor": 1_000,
            "transaction_date": DAY,
        }
    )
    assert patch(env, transfer["id"], {"category_id": bonus}).status_code == 422
    spent = env.expense(world["bank"], world["dining"], 2_000, DAY)
    reversal = env.client.post(f"{API}/transactions/{spent['id']}/reverse", headers=key()).json()["data"]
    assert patch(env, spent["id"], {"category_id": world["travel"]}, version="1").status_code == 422
    assert patch(env, reversal["id"], {"category_id": world["travel"]}).status_code == 422


# ------------------------------------------------- hardening (review round 1)


def test_idempotency_key_is_independent_per_endpoint(env: ApiEnv, world: dict[str, str]) -> None:
    shared = {"Idempotency-Key": "same-client-key"}
    body = {
        "kind": "expense",
        "account_id": world["bank"],
        "category_id": world["dining"],
        "amount_minor": 5_000,
        "transaction_date": DAY,
    }
    created = env.client.post(f"{API}/transactions", json=body, headers=shared)
    assert created.status_code == 201
    reversed_ = env.client.post(f"{API}/transactions/{created.json()['data']['id']}/reverse", headers=shared)
    assert reversed_.status_code == 201  # not mistaken for a replay of the create call
    assert reversed_.json()["data"]["entry_type"] == "REVERSAL"
    assert (
        env.client.post(f"{API}/transactions", json=body, headers=shared).json()["data"]["id"]
        == (created.json()["data"]["id"])
    )


def test_client_key_cannot_collide_with_internal_keys(env: ApiEnv, world: dict[str, str]) -> None:
    spent = env.expense(world["bank"], world["dining"], 5_000, DAY)
    entry_key = env.sql(
        "SELECT idempotency_key FROM journal_entries WHERE id = ?", (spent["journal_entry_id"],)
    )
    assert entry_key[0][0].startswith("api:POST /transactions:")
    opening = env.sql("SELECT idempotency_key FROM journal_entries WHERE entry_type = 'OPENING_BALANCE'")
    assert opening[0][0].startswith("opening-balance:")
    body = {
        "kind": "expense",
        "account_id": world["bank"],
        "category_id": world["dining"],
        "amount_minor": 1,
        "transaction_date": DAY,
    }
    attempt = env.client.post(
        f"{API}/transactions", json=body, headers={"Idempotency-Key": f"opening-balance:{world['bank']}"}
    )
    assert attempt.status_code == 201


def test_idempotency_key_reused_with_different_arguments_is_409(env: ApiEnv, world: dict[str, str]) -> None:
    headers = key()
    body = {
        "kind": "expense",
        "account_id": world["bank"],
        "category_id": world["dining"],
        "amount_minor": 5_000,
        "transaction_date": DAY,
    }
    assert env.client.post(f"{API}/transactions", json=body, headers=headers).status_code == 201
    clash = env.client.post(f"{API}/transactions", json={**body, "amount_minor": 6_000}, headers=headers)
    assert clash.status_code == 409
    assert clash.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


@pytest.mark.parametrize("length", [0, 129])
def test_idempotency_key_length_bounds(env: ApiEnv, world: dict[str, str], length: int) -> None:
    body = {
        "kind": "expense",
        "account_id": world["bank"],
        "category_id": world["dining"],
        "amount_minor": 1,
        "transaction_date": DAY,
    }
    response = env.client.post(f"{API}/transactions", json=body, headers={"Idempotency-Key": "k" * length})
    assert response.status_code == 400


def _cursor(payload: object) -> str:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


@pytest.mark.parametrize(
    "cursor",
    [
        _cursor("not json at all"),
        _cursor(["2026-11-01"]),
        _cursor(["2026-11-01", "id", "extra"]),
        _cursor([1, 2]),
        _cursor(["2026-11-01", 7]),
        _cursor(["not-a-date", "id"]),
        _cursor({"a": 1}),
        "@@@",
    ],
)
def test_garbage_cursors_are_422(env: ApiEnv, cursor: str) -> None:
    response = env.client.get(f"{API}/transactions", params={"cursor": cursor})
    assert response.status_code == 422, cursor
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_like_wildcards_in_q_match_literally(env: ApiEnv, world: dict[str, str]) -> None:
    env.expense(world["bank"], world["dining"], 100, DAY, description="50% off")
    env.expense(world["bank"], world["dining"], 200, DAY, description="snake_case")
    env.expense(world["bank"], world["dining"], 300, DAY, description="plain")

    def amounts(q: str) -> list[int]:
        rows = env.client.get(f"{API}/transactions", params={"q": q}).json()["data"]
        return sorted(r["amount_minor"] for r in rows)

    assert amounts("%") == [100]
    assert amounts("_") == [200]
    assert amounts("\\") == []


def test_unmapped_value_error_returns_a_fixed_message(env: ApiEnv) -> None:
    @env.app.get("/leaky")
    async def leaky() -> None:
        raise ValueError("internal detail: /srv/secret/path")

    response = env.anon.get("/leaky")
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "The request could not be processed."
    assert "secret" not in response.text
