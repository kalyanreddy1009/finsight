from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.api.v1 import statements
from tests.api_helpers import API, ApiEnv, build_env, key

MASTER_KEY = "ab" * 32
CSV_HEADER = "date,description,debit,credit,balance"
CSV_ROWS = [
    "02/11/2026,Salary,,5000.00,15000.00",
    "03/11/2026,Grocery,1200.50,,13799.50",
    "05/11/2026,Cafe,300.00,,13499.50",
]
CLOSING_MINOR = 1_349_950
OPENING_MINOR = 1_000_000


def statement_csv(rows: list[str] = CSV_ROWS) -> bytes:
    return ("\n".join([CSV_HEADER, *rows]) + "\n").encode("utf-8")


@pytest.fixture
def env(tmp_path: Path) -> Iterator[ApiEnv]:
    built = build_env(tmp_path, master_key=MASTER_KEY, docs_dir=str(tmp_path / "docs"))
    yield built
    built.assert_ledger_clean()


@pytest.fixture
def account(env: ApiEnv) -> str:
    return env.account("HDFC")


def upload(
    env: ApiEnv,
    account_id: str,
    content: bytes | None = None,
    *,
    kind: str = "CSV",
    name: str = "statement.csv",
) -> Any:
    payload = statement_csv() if content is None else content
    return env.client.post(
        f"{API}/statements/upload",
        data={"account_id": account_id, "statement_kind": kind},
        files={"file": (name, payload, "text/csv")},
    )


def upload_ok(env: ApiEnv, account_id: str, content: bytes | None = None, name: str = "statement.csv") -> str:
    response = upload(env, account_id, content, name=name)
    assert response.status_code == 201, response.text
    return response.json()["data"]["statement_id"]


def review_rows(env: ApiEnv, statement_id: str) -> list[dict[str, Any]]:
    response = env.client.get(f"{API}/statements/{statement_id}/review")
    assert response.status_code == 200, response.text
    return response.json()["data"]["rows"]


def approve_all(env: ApiEnv, statement_id: str) -> None:
    for row in review_rows(env, statement_id):
        response = env.client.patch(
            f"{API}/statements/rows/{row['id']}", json={"row_status": "USER_APPROVED"}
        )
        assert response.status_code == 200, response.text


def commit(env: ApiEnv, statement_id: str) -> Any:
    return env.client.post(f"{API}/statements/{statement_id}/commit", headers=key())


def account_balance(env: ApiEnv, account_id: str) -> int:
    accounts = env.client.get(f"{API}/accounts").json()["data"]
    return next(a["current_balance_minor"] for a in accounts if a["id"] == account_id)


# --------------------------------------------------------------- upload


def test_upload_csv_returns_ingest_counts(env: ApiEnv, account: str) -> None:
    response = upload(env, account)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert set(data) == {
        "statement_id", "processing_status", "row_count", "auto_approved_count",
        "pending_review_count", "duplicate_count", "mismatch_count", "reconciliation_diff_minor",
    }  # fmt: skip
    assert data["processing_status"] == "REVIEW_REQUIRED"
    assert data["row_count"] == 3
    assert data["auto_approved_count"] + data["pending_review_count"] == 3
    assert data["duplicate_count"] == 0
    assert data["mismatch_count"] == 0
    assert data["reconciliation_diff_minor"] == 0


def test_same_file_again_is_duplicate_with_existing_id(env: ApiEnv, account: str) -> None:
    first = upload_ok(env, account)
    response = upload(env, account)
    assert response.status_code == 409, response.text
    body = response.json()
    assert body["error"]["code"] == "DUPLICATE_STATEMENT"
    assert body["meta"] == {"statement_id": first}


def test_unknown_account_is_404(env: ApiEnv) -> None:
    response = upload(env, "missing")
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"


def test_oversize_upload_is_413_before_ingest(
    env: ApiEnv, account: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(statements, "MAX_UPLOAD_BYTES", 100)
    response = upload(env, account, b"a" * 101)
    assert response.status_code == 413, response.text
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert env.sql("SELECT COUNT(*) FROM statements")[0][0] == 0


def test_upload_at_the_limit_is_accepted(env: ApiEnv, account: str, monkeypatch: pytest.MonkeyPatch) -> None:
    content = statement_csv()
    monkeypatch.setattr(statements, "MAX_UPLOAD_BYTES", len(content))
    assert upload(env, account, content).status_code == 201


def test_non_utf8_binary_is_422(env: ApiEnv, account: str) -> None:
    response = upload(env, account, b"\xff\xfe\x00\x81\x82\x83 binary", name="statement.csv")
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


@pytest.mark.parametrize("overrides", [{}, {"master_key": "abcd"}, {"master_key": "zz" * 32}])
def test_missing_or_invalid_master_key_is_503(tmp_path: Path, overrides: dict[str, str]) -> None:
    env = build_env(tmp_path, docs_dir=str(tmp_path / "docs"), **overrides)
    account_id = env.account("HDFC")
    response = upload(env, account_id)
    assert response.status_code == 503, response.text
    error = response.json()["error"]
    assert error["code"] == "STORAGE_NOT_CONFIGURED"
    assert MASTER_KEY not in error["message"]


def test_client_path_is_reduced_to_base_name(env: ApiEnv, account: str) -> None:
    upload_ok(env, account, name="../../evil.csv")
    listed = env.client.get(f"{API}/statements").json()["data"]
    assert [s["original_filename"] for s in listed] == ["evil.csv"]


def test_all_routes_require_auth(env: ApiEnv, account: str) -> None:
    statement_id = upload_ok(env, account)
    row_id = review_rows(env, statement_id)[0]["id"]
    calls = [
        ("get", f"{API}/statements", {}),
        (
            "post",
            f"{API}/statements/upload",
            {
                "data": {"account_id": account, "statement_kind": "CSV"},
                "files": {"file": ("statement.csv", statement_csv(), "text/csv")},
            },
        ),  # fmt: skip
        ("get", f"{API}/statements/{statement_id}/review", {}),
        ("patch", f"{API}/statements/rows/{row_id}", {"json": {"row_status": "REJECTED"}}),
        ("post", f"{API}/statements/{statement_id}/commit", {"headers": key()}),
    ]
    for method, url, options in calls:
        response = getattr(env.anon, method)(url, **options)
        assert response.status_code == 401, (method, url, response.text)
        assert response.json()["error"]["code"] == "UNAUTHORIZED"


# --------------------------------------------------------------- review


def test_review_returns_summary_rows_and_errors(env: ApiEnv, account: str) -> None:
    statement_id = upload_ok(env, account)
    response = env.client.get(f"{API}/statements/{statement_id}/review")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["statement"]["id"] == statement_id
    assert data["statement"]["closing_balance_minor"] == CLOSING_MINOR
    assert "storage_path" not in data["statement"]
    assert [r["row_index"] for r in data["rows"]] == [0, 1, 2]
    assert [r["amount_minor"] for r in data["rows"]] == [500_000, 120_050, 30_000]
    assert data["import_errors"] == []
    assert env.client.get(f"{API}/statements/missing/review").status_code == 404


def test_approve_and_reject_a_row(env: ApiEnv, account: str) -> None:
    statement_id = upload_ok(env, account)
    row_id = review_rows(env, statement_id)[1]["id"]
    rejected = env.client.patch(f"{API}/statements/rows/{row_id}", json={"row_status": "REJECTED"})
    assert rejected.status_code == 200, rejected.text
    returned = rejected.json()["data"]
    assert returned["id"] == row_id
    assert returned["row_status"] == "REJECTED"
    assert returned == next(r for r in review_rows(env, statement_id) if r["id"] == row_id)
    statuses = {r["id"]: r["row_status"] for r in review_rows(env, statement_id)}
    assert statuses[row_id] == "REJECTED"
    approved = env.client.patch(f"{API}/statements/rows/{row_id}", json={"row_status": "USER_APPROVED"})
    assert approved.status_code == 200, approved.text
    assert {r["id"]: r["row_status"] for r in review_rows(env, statement_id)}[row_id] == "USER_APPROVED"


def test_row_category_must_match_direction(env: ApiEnv, account: str) -> None:
    statement_id = upload_ok(env, account)
    rows = review_rows(env, statement_id)
    dining = env.category("Dining")
    salary = env.category("Salary", "INCOME")
    debit_row, credit_row = rows[1]["id"], rows[0]["id"]
    url = f"{API}/statements/rows"
    ok_response = env.client.patch(f"{url}/{debit_row}", json={"suggested_category_id": dining})
    assert ok_response.status_code == 200, ok_response.text
    wrong = env.client.patch(f"{url}/{credit_row}", json={"suggested_category_id": dining})
    assert wrong.status_code == 422
    right = env.client.patch(f"{url}/{credit_row}", json={"suggested_category_id": salary})
    assert right.status_code == 200, right.text


def test_row_update_error_paths(env: ApiEnv, account: str) -> None:
    statement_id = upload_ok(env, account)
    row_id = review_rows(env, statement_id)[0]["id"]
    url = f"{API}/statements/rows/{row_id}"
    assert env.client.patch(url, json={"row_status": "AUTO_APPROVED"}).status_code == 422
    assert env.client.patch(url, json={"row_status": "REJECTED", "surprise": 1}).status_code == 422
    assert env.client.patch(url, json={}).status_code == 422
    missing = env.client.patch(f"{API}/statements/rows/missing", json={"row_status": "REJECTED"})
    assert missing.status_code == 404


def test_row_cannot_change_after_commit(env: ApiEnv, account: str) -> None:
    statement_id = upload_ok(env, account)
    approve_all(env, statement_id)
    assert commit(env, statement_id).status_code == 201
    row_id = review_rows(env, statement_id)[0]["id"]
    response = env.client.patch(f"{API}/statements/rows/{row_id}", json={"row_status": "REJECTED"})
    assert response.status_code == 422, response.text


# --------------------------------------------------------------- commit


def test_commit_without_idempotency_key_is_400(env: ApiEnv, account: str) -> None:
    statement_id = upload_ok(env, account)
    response = env.client.post(f"{API}/statements/{statement_id}/commit")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MISSING_IDEMPOTENCY_KEY"


def test_commit_with_pending_rows_is_409(env: ApiEnv, account: str) -> None:
    statement_id = upload_ok(env, account)
    assert any(r["row_status"] == "PENDING_REVIEW" for r in review_rows(env, statement_id))
    response = commit(env, statement_id)
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "STATEMENT_NOT_RECONCILED"


def test_commit_unknown_statement_is_404(env: ApiEnv) -> None:
    assert commit(env, "missing").status_code == 404


def test_happy_path_upload_review_approve_commit(env: ApiEnv, account: str) -> None:
    statement_id = upload_ok(env, account)
    approve_all(env, statement_id)

    committed = commit(env, statement_id)
    assert committed.status_code == 201, committed.text
    result = committed.json()["data"]
    assert result["statement_id"] == statement_id
    assert (result["committed_count"], result["skipped_count"], result["already_committed"]) == (3, 0, False)

    transactions = env.client.get(f"{API}/transactions").json()["data"]
    amounts = sorted(t["amount_minor"] for t in transactions if t["entry_type"] != "OPENING_BALANCE")
    assert amounts == [30_000, 120_050, 500_000]
    assert account_balance(env, account) == CLOSING_MINOR
    assert CLOSING_MINOR == OPENING_MINOR + 500_000 - 120_050 - 30_000

    replay = commit(env, statement_id)
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["already_committed"] is True
    assert account_balance(env, account) == CLOSING_MINOR
    env.assert_ledger_clean()


# --------------------------------------------------------------- listing


def test_list_filters_and_never_exposes_storage_fields(env: ApiEnv, account: str) -> None:
    other = env.account("SBI", "BANK_CURRENT")
    first = upload_ok(env, account)
    second_content = statement_csv(["04/11/2026,Fuel,500.00,,12999.50"])
    second = upload_ok(env, other, second_content, name="sbi.csv")

    listed = env.client.get(f"{API}/statements").json()["data"]
    assert {s["id"] for s in listed} == {first, second}
    assert all("storage_path" not in s and "file_hash_sha256" not in s for s in listed)
    expected_fields = {
        "id", "account_id", "statement_kind", "original_filename", "statement_start_date",
        "statement_end_date", "opening_balance_minor", "closing_balance_minor",
        "reconciliation_diff_minor", "processing_status", "uploaded_at", "approved_at",
    }  # fmt: skip
    assert set(listed[0]) == expected_fields

    by_account = env.client.get(f"{API}/statements", params={"account_id": other}).json()["data"]
    assert [s["id"] for s in by_account] == [second]
    approved = env.client.get(f"{API}/statements", params={"processing_status": "APPROVED"}).json()["data"]
    assert approved == []
    assert env.client.get(f"{API}/statements", params={"limit": 0}).status_code == 422
    assert env.client.get(f"{API}/statements", params={"processing_status": "NOPE"}).status_code == 422
