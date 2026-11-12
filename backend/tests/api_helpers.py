"""Shared helpers for the API tests: app + authenticated client over a temp-file DB, fake clock."""

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.database.session import connect
from app.finance.ledger_service import LedgerService
from app.main import create_app

API = "/api/v1"
PASSWORD = "correct horse battery"
SETUP_TOKEN = "setup-token-for-tests"
JWT_SECRET = "test-secret-" + "x" * 40
ORIGIN = "https://app.finsight.test"
IST = timezone(timedelta(hours=5, minutes=30))
START = datetime(2026, 11, 12, 10, 0, tzinfo=IST)


@dataclass
class FakeClock:
    now: datetime = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now = self.now + timedelta(**delta)


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "db_path": str(tmp_path / "api.db"),
        "jwt_secret": JWT_SECRET,
        "allowed_origins": [ORIGIN],
        "setup_token": SETUP_TOKEN,
    }
    return Settings(**{**values, **overrides})


def make_client(app: FastAPI, address: str = "testclient") -> TestClient:
    # https base URL so the Secure refresh cookie is sent back; 500s are returned, not re-raised.
    return TestClient(
        app, base_url="https://testserver", raise_server_exceptions=False, client=(address, 50000)
    )


def setup_body(**overrides: Any) -> dict[str, Any]:
    return {"password": PASSWORD, "device_name": "Test browser", "setup_token": SETUP_TOKEN, **overrides}


def key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


@dataclass
class ApiEnv:
    app: FastAPI
    client: TestClient
    anon: TestClient
    clock: FakeClock
    settings: Settings
    token: str
    device_id: str

    @contextmanager
    def db(self) -> Iterator[sqlite3.Connection]:
        conn = connect(self.settings.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def sql(self, statement: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self.db() as conn:
            return conn.execute(statement, params).fetchall()

    def assert_ledger_clean(self) -> None:
        with self.db() as conn:
            report = LedgerService(conn).verify_integrity()
        assert report.is_clean, report

    # ------------------------------------------------------------ API shortcuts

    def post(self, path: str, body: dict[str, Any], expect: int = 201, **headers: str) -> dict[str, Any]:
        response = self.client.post(f"{API}{path}", json=body, headers=headers)
        assert response.status_code == expect, response.text
        return response.json()

    def account(self, name: str, subtype: str = "BANK_SAVINGS", **extra: Any) -> str:
        return self.post("/accounts", {"name": name, "account_subtype": subtype, **extra})["data"]["id"]

    def category(self, name: str, category_type: str = "EXPENSE") -> str:
        return self.post("/categories", {"name": name, "category_type": category_type})["data"]["id"]

    def transaction(self, body: dict[str, Any], **headers: str) -> dict[str, Any]:
        merged = {**key(), **headers}
        return self.post("/transactions", body, **merged)["data"]

    def expense(
        self, account_id: str, category_id: str, amount: int, day: str, **extra: Any
    ) -> dict[str, Any]:
        body = {
            "kind": "expense",
            "account_id": account_id,
            "category_id": category_id,
            "amount_minor": amount,
            "transaction_date": day,
            **extra,
        }
        return self.transaction(body)


def build_env(tmp_path: Path, **setting_overrides: Any) -> ApiEnv:
    settings = make_settings(tmp_path, **setting_overrides)
    clock = FakeClock()
    app = create_app(settings, clock=clock)
    client = make_client(app)
    anon = make_client(app)
    response = client.post(f"{API}/auth/setup", json=setup_body())
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    client.headers["Authorization"] = f"Bearer {data['access_token']}"
    return ApiEnv(app, client, anon, clock, settings, data["access_token"], data["device_id"])
