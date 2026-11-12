"""Password authentication with rotating refresh tokens (single owner, browser client)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, Header, Response

from app.api import auth_service
from app.api.deps import ClockDep, Conn, DeviceId, SettingsDep, ThrottleDep
from app.api.envelope import ok
from app.api.errors import ApiError, not_found
from app.api.v1.schemas import DeviceRevokeIn, LoginIn, SetupIn
from app.core import security
from app.core.config import Settings

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "fs_refresh"
REFRESH_PATH = "/api/v1/auth"
CSRF_HEADER_VALUE = "finsight"
_THROTTLE_KEY = "owner"


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


@router.post("/setup", status_code=201)
async def setup(
    body: SetupIn, response: Response, conn: Conn, clock: ClockDep, settings: SettingsDep
) -> dict:
    now = clock()
    device_id, refresh = auth_service.create_owner(conn, body.password, body.device_name, now)
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
) -> dict:
    if throttle.is_locked(_THROTTLE_KEY):
        raise ApiError(
            429,
            "TOO_MANY_ATTEMPTS",
            "Too many failed sign-in attempts. Try again later.",
            headers={"Retry-After": str(security.THROTTLE_WINDOW_SECONDS)},
        )
    if not security.verify_password(body.password, auth_service.get_password_hash(conn)):
        throttle.record_failure(_THROTTLE_KEY)
        raise ApiError(401, "INVALID_CREDENTIALS", "Invalid credentials.")
    throttle.reset(_THROTTLE_KEY)
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
        raise auth_service.invalid_refresh()
    now = clock()
    try:
        device_id, replacement = auth_service.rotate_refresh(conn, fs_refresh, now)
    except ApiError:
        response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
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
