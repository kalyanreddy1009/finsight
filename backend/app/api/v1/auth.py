"""Password authentication with rotating refresh tokens (single owner, browser client)."""

import hmac
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, Header, Response
from pydantic import Field, StrictStr

from app.api import auth_service
from app.api.deps import ClientAddress, ClockDep, Conn, DeviceId, SettingsDep, ThrottleDep
from app.api.envelope import ok
from app.api.errors import ApiError, not_found
from app.api.v1.schemas import DeviceRevokeIn, LoginIn, SetupIn
from app.core import security
from app.core.config import Settings

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "fs_refresh"
REFRESH_PATH = "/api/v1/auth"
CSRF_HEADER_VALUE = "finsight"


class SetupWithTokenIn(SetupIn):
    setup_token: Annotated[StrictStr, Field(min_length=1, max_length=256)]


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=security.REFRESH_TOKEN_TTL_SECONDS,
        path=REFRESH_PATH,
        httponly=True,
        secure=True,
        samesite="strict",
    )


def _session_payload(device_id: str, settings: Settings, now: datetime) -> dict[str, object]:
    secret = security.validate_jwt_secret(
        settings.jwt_secret.get_secret_value() if settings.jwt_secret else None
    )
    return {
        "access_token": security.create_access_token(device_id, secret, now.timestamp()),
        "token_type": "Bearer",
        "expires_in": security.ACCESS_TOKEN_TTL_SECONDS,
        "device_id": device_id,
    }


@router.get("/status")
async def status(conn: Conn) -> dict:
    return ok({"configured": auth_service.is_configured(conn)})


def _locked_out() -> ApiError:
    return ApiError(
        429,
        "TOO_MANY_ATTEMPTS",
        "Too many failed attempts. Try again later.",
        headers={"Retry-After": str(security.THROTTLE_WINDOW_SECONDS)},
    )


def _clear_cookie_header() -> dict[str, str]:
    scratch = Response()
    scratch.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH, secure=True, httponly=True, samesite="strict")
    return {"set-cookie": scratch.headers["set-cookie"]}


async def _check_setup_token(
    presented: str, settings: Settings, throttle: security.LoginThrottle, address: str
) -> None:
    if settings.setup_token is None:
        raise ApiError(503, "SETUP_TOKEN_NOT_CONFIGURED", "First-run setup is not enabled on this server.")
    if throttle.is_locked(address):
        raise _locked_out()
    expected = settings.setup_token.get_secret_value().encode("utf-8")
    if not hmac.compare_digest(presented.encode("utf-8"), expected):
        throttle.record_failure(address)
        raise ApiError(403, "INVALID_SETUP_TOKEN", "Invalid setup token.")


@router.post("/setup", status_code=201)
async def setup(
    body: SetupWithTokenIn,
    response: Response,
    conn: Conn,
    clock: ClockDep,
    settings: SettingsDep,
    throttle: ThrottleDep,
    address: ClientAddress,
) -> dict:
    if auth_service.is_configured(conn):
        raise ApiError(409, "ALREADY_CONFIGURED", "FinSight is already set up.")
    await _check_setup_token(body.setup_token, settings, throttle, address)
    password_hash = await security.hash_password_async(body.password)
    now = clock()
    device_id, refresh = auth_service.create_owner(conn, password_hash, body.device_name, now)
    _set_refresh_cookie(response, refresh)
    return ok(_session_payload(device_id, settings, now))


@router.post("/login")
async def login(
    body: LoginIn,
    response: Response,
    conn: Conn,
    clock: ClockDep,
    settings: SettingsDep,
    throttle: ThrottleDep,
    address: ClientAddress,
) -> dict:
    if throttle.is_locked(address):
        raise _locked_out()
    if not await security.verify_password_async(body.password, auth_service.get_password_hash(conn)):
        throttle.record_failure(address)
        raise ApiError(401, "INVALID_CREDENTIALS", "Invalid credentials.")
    throttle.reset(address)
    now = clock()
    device_id, refresh = auth_service.create_session(conn, body.device_name, now)
    _set_refresh_cookie(response, refresh)
    return ok(_session_payload(device_id, settings, now))


@router.post("/refresh")
async def refresh(
    response: Response,
    conn: Conn,
    clock: ClockDep,
    settings: SettingsDep,
    x_requested_with: Annotated[str | None, Header()] = None,
    fs_refresh: Annotated[str | None, Cookie()] = None,
) -> dict:
    if x_requested_with != CSRF_HEADER_VALUE:
        raise ApiError(403, "CSRF_CHECK_FAILED", "Missing or invalid X-Requested-With header.")
    if not fs_refresh:
        raise auth_service.RefreshRejected(clear_cookie=False)
    now = clock()
    try:
        device_id, replacement = auth_service.rotate_refresh(conn, fs_refresh, now)
    except auth_service.RefreshRejected as rejected:
        # The cookie is only cleared when the session is gone; never on the benign stale-token path.
        rejected.headers = _clear_cookie_header() if rejected.clear_cookie else None
        raise
    _set_refresh_cookie(response, replacement)
    return ok(_session_payload(device_id, settings, now))


@router.post("/logout")
async def logout(response: Response, conn: Conn, clock: ClockDep, device_id: DeviceId) -> dict:
    auth_service.revoke_device(conn, device_id, device_id, clock(), "LOGOUT")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    return ok({"revoked": True})


@router.get("/devices")
async def devices(conn: Conn, device_id: DeviceId) -> dict:
    rows = auth_service.list_devices(conn)
    return ok(
        [
            {
                "id": r["id"],
                "device_name": r["device_name"],
                "platform": r["platform"],
                "created_at": r["created_at"],
                "last_seen_at": r["last_seen_at"],
                "is_revoked": bool(r["is_revoked"]),
                "is_current": r["id"] == device_id,
            }
            for r in rows
        ]
    )


@router.post("/device-revoke")
async def device_revoke(body: DeviceRevokeIn, conn: Conn, clock: ClockDep, device_id: DeviceId) -> dict:
    if not auth_service.revoke_device(conn, body.device_id, device_id, clock(), "OWNER_REQUEST"):
        raise not_found("Device")
    return ok({"device_id": body.device_id, "is_revoked": True})
