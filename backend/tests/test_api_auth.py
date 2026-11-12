from collections.abc import Iterator
from pathlib import Path

import jwt
import pytest

from app.core import security
from app.core.config import Settings
from app.main import create_app
from tests.api_helpers import (
    API,
    JWT_SECRET,
    ORIGIN,
    PASSWORD,
    ApiEnv,
    FakeClock,
    build_env,
    make_client,
    make_settings,
    setup_body,
)

CSRF = {"X-Requested-With": "finsight"}


@pytest.fixture
def env(tmp_path: Path) -> Iterator[ApiEnv]:
    yield build_env(tmp_path)


def login(client, password: str = PASSWORD, name: str = "Other browser"):
    return client.post(f"{API}/auth/login", json={"password": password, "device_name": name})


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ startup


def test_create_app_requires_a_long_enough_jwt_secret(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="FINSIGHT_JWT_SECRET"):
        create_app(Settings(db_path=str(tmp_path / "a.db")))
    with pytest.raises(RuntimeError, match="FINSIGHT_JWT_SECRET"):
        create_app(Settings(db_path=str(tmp_path / "b.db"), jwt_secret="short"))


def test_create_app_rejects_wildcard_origin(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS"):
        create_app(make_settings(tmp_path, allowed_origins=["*"]))


def test_health_is_public_and_enveloped(env: ApiEnv) -> None:
    body = env.anon.get(f"{API}/health").json()
    assert body == {"data": {"status": "ok"}, "error": None, "meta": None}


def test_cors_allows_only_configured_origins(env: ApiEnv) -> None:
    ask = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization"}
    allowed = env.anon.options(f"{API}/accounts", headers={"Origin": ORIGIN, **ask})
    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    assert allowed.headers["access-control-allow-credentials"] == "true"
    denied = env.anon.options(f"{API}/accounts", headers={"Origin": "https://evil.test", **ask})
    assert "access-control-allow-origin" not in denied.headers


def test_unknown_route_and_server_errors_use_the_envelope(env: ApiEnv) -> None:
    missing = env.anon.get(f"{API}/nope")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"

    @env.app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internals /etc/passwd")

    crashed = env.anon.get("/boom")
    assert crashed.status_code == 500
    assert crashed.json() == {
        "data": None,
        "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."},
        "meta": None,
    }
    assert "internals" not in crashed.text


# -------------------------------------------------------------------- setup


def test_setup_runs_once_and_reports_status(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path), clock=FakeClock())
    client = make_client(app)
    assert client.get(f"{API}/auth/status").json()["data"] == {"configured": False}
    weak = client.post(f"{API}/auth/setup", json=setup_body(password="short"))
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "VALIDATION_ERROR"

    first = client.post(f"{API}/auth/setup", json=setup_body(device_name="Laptop"))
    assert first.status_code == 201
    assert client.get(f"{API}/auth/status").json()["data"] == {"configured": True}
    second = client.post(f"{API}/auth/setup", json=setup_body(password="another long password"))
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "ALREADY_CONFIGURED"


def test_password_is_stored_as_argon2id_only(env: ApiEnv) -> None:
    stored = env.sql("SELECT password_hash FROM owner_credentials")[0][0]
    assert stored.startswith("$argon2id$")
    assert PASSWORD not in stored


def test_login_before_setup_is_generic_401(tmp_path: Path) -> None:
    client = make_client(create_app(make_settings(tmp_path), clock=FakeClock()))
    response = login(client)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


# -------------------------------------------------------------------- login


def test_login_returns_access_token_and_hardened_refresh_cookie(env: ApiEnv) -> None:
    response = login(env.anon)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] == 900
    claims = jwt.decode(data["access_token"], JWT_SECRET, algorithms=["HS256"], options={"verify_exp": False})
    assert claims["sub"] == data["device_id"]
    assert claims["jti"]
    assert claims["exp"] == int(env.clock().timestamp()) + 900

    cookie = response.headers["set-cookie"]
    for attribute in (
        "fs_refresh=",
        "HttpOnly",
        "Secure",
        "SameSite=strict",
        "Path=/api/v1/auth",
        "Max-Age=2592000",
    ):
        assert attribute in cookie
    refresh = env.anon.cookies["fs_refresh"]
    stored = env.sql("SELECT refresh_token_hash FROM devices WHERE id = ?", (data["device_id"],))[0][0]
    assert stored == security.hash_refresh_token(refresh)
    assert refresh not in stored


def test_wrong_password_is_generic_and_identical(env: ApiEnv) -> None:
    wrong = login(env.anon, "definitely wrong password")
    assert wrong.status_code == 401
    assert wrong.json() == {
        "data": None,
        "error": {"code": "INVALID_CREDENTIALS", "message": "Invalid credentials."},
        "meta": None,
    }


def test_login_is_throttled_after_five_failures_for_the_window(env: ApiEnv) -> None:
    for _ in range(5):
        assert login(env.anon, "wrong password here").status_code == 401
    locked = login(env.anon)  # even the right password is refused inside the window
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
    env.clock.advance(minutes=14)
    assert login(env.anon).status_code == 429
    env.clock.advance(minutes=2)
    assert login(env.anon).status_code == 200


def test_successful_login_resets_the_failure_count(env: ApiEnv) -> None:
    for _ in range(4):
        login(env.anon, "wrong password here")
    assert login(env.anon).status_code == 200
    for _ in range(4):
        login(env.anon, "wrong password here")
    assert login(env.anon).status_code == 200


def test_login_validates_body(env: ApiEnv) -> None:
    response = env.anon.post(f"{API}/auth/login", json={"password": 12345678, "device_name": "x"})
    assert response.status_code == 422


# ------------------------------------------------------------ bearer tokens


@pytest.mark.parametrize("header", [None, "", "Bearer", "Bearer not-a-jwt", "Basic abc"])
def test_missing_or_malformed_bearer_is_401(env: ApiEnv, header: str | None) -> None:
    headers = {"Authorization": header} if header is not None else {}
    response = env.anon.get(f"{API}/accounts", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.headers["www-authenticate"] == "Bearer"


def test_token_signed_with_another_secret_is_rejected(env: ApiEnv) -> None:
    forged = security.create_access_token(env.device_id, "y" * 40, env.clock().timestamp())
    assert env.anon.get(f"{API}/accounts", headers=bearer(forged)).status_code == 401


def test_expired_access_token_is_rejected(env: ApiEnv) -> None:
    assert env.client.get(f"{API}/accounts").status_code == 200
    env.clock.advance(minutes=14, seconds=59)
    assert env.client.get(f"{API}/accounts").status_code == 200
    env.clock.advance(seconds=2)
    response = env.client.get(f"{API}/accounts")
    assert response.status_code == 401


def test_token_for_unknown_device_is_rejected(env: ApiEnv) -> None:
    ghost = security.create_access_token("no-such-device", JWT_SECRET, env.clock().timestamp())
    assert env.anon.get(f"{API}/accounts", headers=bearer(ghost)).status_code == 401


# ------------------------------------------------------------------ refresh


def test_refresh_requires_csrf_header_and_cookie(env: ApiEnv) -> None:
    assert env.client.post(f"{API}/auth/refresh").status_code == 403
    assert env.anon.post(f"{API}/auth/refresh", headers=CSRF).status_code == 401


def test_refresh_rotates_the_token(env: ApiEnv) -> None:
    old = env.client.cookies["fs_refresh"]
    env.clock.advance(minutes=20)
    response = env.client.post(f"{API}/auth/refresh", headers=CSRF)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["device_id"] == env.device_id
    new = env.client.cookies["fs_refresh"]
    assert new != old
    stored = env.sql("SELECT refresh_token_hash FROM devices WHERE id = ?", (env.device_id,))[0][0]
    assert stored == security.hash_refresh_token(new)
    assert env.anon.get(f"{API}/accounts", headers=bearer(data["access_token"])).status_code == 200


def test_reusing_a_rotated_refresh_token_revokes_the_device(env: ApiEnv) -> None:
    stolen = env.client.cookies["fs_refresh"]
    rotated = env.client.post(f"{API}/auth/refresh", headers=CSRF)
    assert rotated.status_code == 200
    fresh_access = rotated.json()["data"]["access_token"]
    env.clock.advance(seconds=31)  # outside the grace window

    replay = env.anon.post(f"{API}/auth/refresh", headers={**CSRF, "Cookie": f"fs_refresh={stolen}"})
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"
    assert "fs_refresh" in replay.headers["set-cookie"]  # cookie cleared: the session is gone
    assert env.sql("SELECT is_revoked FROM devices WHERE id = ?", (env.device_id,))[0][0] == 1
    # The legitimate (rotated) session is dead too, including its access token.
    assert env.anon.get(f"{API}/accounts", headers=bearer(fresh_access)).status_code == 401
    assert env.client.post(f"{API}/auth/refresh", headers=CSRF).status_code == 401
    events = env.sql("SELECT metadata_json FROM audit_events WHERE event_type = 'DEVICE_REVOKED'")
    assert len(events) == 1
    assert "REFRESH_TOKEN_REUSE" in events[0][0]


def test_refresh_token_idle_for_over_30_days_is_rejected(env: ApiEnv) -> None:
    env.clock.advance(days=31)
    response = env.client.post(f"{API}/auth/refresh", headers=CSRF)
    assert response.status_code == 401


def test_garbage_refresh_cookie_is_401(env: ApiEnv) -> None:
    for value in ("garbage", "no-such-device.secret"):
        response = env.anon.post(f"{API}/auth/refresh", headers={**CSRF, "Cookie": f"fs_refresh={value}"})
        assert response.status_code == 401


# ------------------------------------------------- logout, devices, audit


def test_logout_revokes_the_session_immediately(env: ApiEnv) -> None:
    assert env.client.post(f"{API}/auth/logout").status_code == 200
    assert env.client.get(f"{API}/accounts").status_code == 401
    assert env.client.post(f"{API}/auth/refresh", headers=CSRF).status_code == 401


def test_device_list_and_revoke_other_device(env: ApiEnv) -> None:
    other = login(env.anon).json()["data"]
    listing = env.client.get(f"{API}/auth/devices").json()["data"]
    assert {d["id"] for d in listing} == {env.device_id, other["device_id"]}
    assert [d["id"] for d in listing if d["is_current"]] == [env.device_id]
    assert all(d["platform"] == "WEB_ADMIN" for d in listing)

    revoked = env.client.post(f"{API}/auth/device-revoke", json={"device_id": other["device_id"]})
    assert revoked.status_code == 200
    assert env.anon.get(f"{API}/accounts", headers=bearer(other["access_token"])).status_code == 401
    assert env.client.get(f"{API}/accounts").status_code == 200  # the revoker is unaffected
    again = env.client.post(f"{API}/auth/device-revoke", json={"device_id": other["device_id"]})
    assert again.status_code == 200
    unknown = env.client.post(f"{API}/auth/device-revoke", json={"device_id": "nope"})
    assert unknown.status_code == 404
    revoked_events = env.sql("SELECT target_object_id FROM audit_events WHERE event_type = 'DEVICE_REVOKED'")
    assert [r[0] for r in revoked_events] == [other["device_id"]]  # revoking twice audits once


def test_audit_events_written_for_logins(env: ApiEnv) -> None:
    login(env.anon)
    rows = env.sql("SELECT actor_device_id FROM audit_events WHERE event_type = 'DEVICE_LOGIN'")
    assert len(rows) == 2  # setup session + this login
    assert env.client.post(f"{API}/auth/device-revoke", json={"device_id": env.device_id}).status_code == 200
    assert env.sql("SELECT COUNT(*) FROM audit_events WHERE event_type = 'DEVICE_REVOKED'")[0][0] == 1


# ------------------------------------------------- refresh grace window


def test_stale_refresh_within_grace_is_refused_without_revoking(env: ApiEnv) -> None:
    first_cookie = env.client.cookies["fs_refresh"]
    first = env.client.post(f"{API}/auth/refresh", headers=CSRF)
    assert first.status_code == 200
    second = env.anon.post(f"{API}/auth/refresh", headers={**CSRF, "Cookie": f"fs_refresh={first_cookie}"})
    assert second.status_code == 401
    assert second.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"
    assert "set-cookie" not in second.headers  # the browser keeps the cookie from the first refresh
    assert env.sql("SELECT is_revoked FROM devices WHERE id = ?", (env.device_id,))[0][0] == 0
    assert env.sql("SELECT COUNT(*) FROM audit_events WHERE event_type = 'DEVICE_REVOKED'")[0][0] == 0
    access = first.json()["data"]["access_token"]
    assert env.anon.get(f"{API}/accounts", headers=bearer(access)).status_code == 200
    assert env.client.post(f"{API}/auth/refresh", headers=CSRF).status_code == 200


def test_stale_refresh_after_grace_revokes(env: ApiEnv) -> None:
    first_cookie = env.client.cookies["fs_refresh"]
    assert env.client.post(f"{API}/auth/refresh", headers=CSRF).status_code == 200
    env.clock.advance(seconds=security.REFRESH_REUSE_GRACE_SECONDS + 1)
    late = env.anon.post(f"{API}/auth/refresh", headers={**CSRF, "Cookie": f"fs_refresh={first_cookie}"})
    assert late.status_code == 401
    assert env.sql("SELECT is_revoked FROM devices WHERE id = ?", (env.device_id,))[0][0] == 1


def test_only_the_immediate_predecessor_is_tolerated(env: ApiEnv) -> None:
    oldest = env.client.cookies["fs_refresh"]
    env.client.post(f"{API}/auth/refresh", headers=CSRF)
    env.client.post(f"{API}/auth/refresh", headers=CSRF)
    replay = env.anon.post(f"{API}/auth/refresh", headers={**CSRF, "Cookie": f"fs_refresh={oldest}"})
    assert replay.status_code == 401
    assert env.sql("SELECT is_revoked FROM devices WHERE id = ?", (env.device_id,))[0][0] == 1


def test_session_older_than_90_days_cannot_refresh(env: ApiEnv) -> None:
    for _ in range(3):  # stay active so only the absolute lifetime can end the session
        env.clock.advance(days=25)
        assert env.client.post(f"{API}/auth/refresh", headers=CSRF).status_code == 200
    env.clock.advance(days=16)  # 91 days after sign-in
    response = env.client.post(f"{API}/auth/refresh", headers=CSRF)
    assert response.status_code == 401
    assert env.sql("SELECT is_revoked FROM devices WHERE id = ?", (env.device_id,))[0][0] == 1
    reasons = env.sql("SELECT metadata_json FROM audit_events WHERE event_type = 'DEVICE_REVOKED'")
    assert "SESSION_LIFETIME_EXCEEDED" in reasons[0][0]


# ----------------------------------------------------- per-address throttle


def test_throttle_is_per_address(env: ApiEnv) -> None:
    attacker = make_client(env.app, "203.0.113.9")
    for _ in range(5):
        assert login(attacker, "wrong password here").status_code == 401
    assert login(attacker).status_code == 429
    owner = make_client(env.app, "198.51.100.7")
    assert login(owner).status_code == 200


def test_forwarded_for_header_is_not_trusted(env: ApiEnv) -> None:
    attacker = make_client(env.app, "203.0.113.9")
    for index in range(5):
        attacker.post(
            f"{API}/auth/login",
            json={"password": "wrong password here", "device_name": "x"},
            headers={"X-Forwarded-For": f"10.0.0.{index}"},
        )
    assert login(attacker).status_code == 429


def test_global_failure_ceiling_blocks_everyone(env: ApiEnv) -> None:
    for index in range(10):  # 10 addresses x 5 failures = 50
        client = make_client(env.app, f"192.0.2.{index}")
        for _ in range(5):
            assert login(client, "wrong password here").status_code == 401
    owner = make_client(env.app, "198.51.100.7")
    assert login(owner).status_code == 429
    env.clock.advance(minutes=16)
    assert login(owner).status_code == 200


# ----------------------------------------------------------- setup token

SETUP_URL = f"{API}/auth/setup"


def fresh_app_client(tmp_path: Path, **overrides):
    app = create_app(make_settings(tmp_path, **overrides), clock=FakeClock())
    return app, make_client(app)


def test_setup_requires_the_setup_token(tmp_path: Path) -> None:
    _, client = fresh_app_client(tmp_path)
    body = setup_body()
    del body["setup_token"]
    assert client.post(SETUP_URL, json=body).status_code == 422
    wrong = client.post(SETUP_URL, json=setup_body(setup_token="not-the-token"))
    assert wrong.status_code == 403
    assert wrong.json()["error"]["code"] == "INVALID_SETUP_TOKEN"
    assert client.get(f"{API}/auth/status").json()["data"] == {"configured": False}
    assert client.post(SETUP_URL, json=setup_body()).status_code == 201


def test_setup_disabled_when_token_not_configured(tmp_path: Path) -> None:
    _, client = fresh_app_client(tmp_path, setup_token=None)
    response = client.post(SETUP_URL, json=setup_body())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SETUP_TOKEN_NOT_CONFIGURED"
    assert client.get(f"{API}/auth/status").json()["data"] == {"configured": False}


def test_wrong_setup_tokens_are_throttled_per_address(tmp_path: Path) -> None:
    app, client = fresh_app_client(tmp_path)
    for _ in range(5):
        assert client.post(SETUP_URL, json=setup_body(setup_token="guess")).status_code == 403
    assert client.post(SETUP_URL, json=setup_body()).status_code == 429  # even the right token
    other = make_client(app, "198.51.100.7")
    assert other.post(SETUP_URL, json=setup_body()).status_code == 201


# ------------------------------------------------------------ JWT negatives


def _forge(claims: dict, secret: str = JWT_SECRET, algorithm: str = "HS256") -> str:
    key = None if algorithm == "none" else secret
    return jwt.encode(claims, key, algorithm=algorithm)


def test_malformed_jwts_are_rejected(env: ApiEnv) -> None:
    exp = int(env.clock().timestamp()) + 600
    valid = {"sub": env.device_id, "jti": "j", "exp": exp}
    good = _forge(valid)
    head, _payload, signature = good.split(".")
    tampered_payload = _forge({**valid, "sub": "someone-else"}).split(".")[1]
    candidates = {
        "alg_none": _forge(valid, algorithm="none"),
        "missing_exp": _forge({"sub": env.device_id, "jti": "j"}),
        "missing_sub": _forge({"jti": "j", "exp": exp}),
        "tampered_payload": f"{head}.{tampered_payload}.{signature}",
        "non_string_sub": _forge({**valid, "sub": 12345}),
        "other_secret": _forge(valid, secret="z" * 40),
        "expired": _forge({**valid, "exp": exp - 3600}),
    }
    assert env.anon.get(f"{API}/accounts", headers=bearer(good)).status_code == 200  # control
    for name, token in candidates.items():
        response = env.anon.get(f"{API}/accounts", headers=bearer(token))
        assert response.status_code == 401, name
