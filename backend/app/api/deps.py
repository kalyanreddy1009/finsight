"""FastAPI dependencies: settings, per-request DB connection, clock and bearer authentication.

Handlers are ``async`` on purpose: the connection dependency and the handler then run on the same
event-loop thread, which a sqlite3 connection requires. A single-owner app does not need more.
"""

import sqlite3
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Header, Request

from app.api import auth_service
from app.api.errors import ApiError, unauthorized
from app.core import security
from app.core.config import Settings
from app.database.session import connect

Clock = Callable[[], datetime]


def default_clock() -> datetime:
    return datetime.now().astimezone()


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_clock(request: Request) -> Clock:
    return request.app.state.clock


async def get_conn(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> AsyncIterator[sqlite3.Connection]:
    key = settings.db_key.get_secret_value() if settings.db_key else None
    conn = connect(settings.db_path, key)
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[sqlite3.Connection, Depends(get_conn)]
ClockDep = Annotated[Clock, Depends(get_clock)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def _bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise unauthorized()
    return token.strip()


async def current_device_id(request: Request, conn: Conn, clock: ClockDep, settings: SettingsDep) -> str:
    """Validate the bearer token and that its device is still active (checked on every request)."""
    secret = settings.jwt_secret.get_secret_value() if settings.jwt_secret else ""
    try:
        device_id = security.decode_access_token(_bearer_token(request), secret, clock().timestamp())
    except security.TokenError:
        raise unauthorized("Invalid or expired access token.") from None
    if auth_service.find_active_device(conn, device_id) is None:
        raise unauthorized("Session has been revoked.")
    return device_id


DeviceId = Annotated[str, Depends(current_device_id)]


_KEY_MAX_LENGTH = 128


def idempotency_key(
    request: Request, _device: DeviceId, idempotency_key: Annotated[str | None, Header()] = None
) -> str:
    """Return the client's key namespaced by method and route, so it cannot collide with another
    endpoint's key or an internal ledger key (``opening-balance:*``, ``recategorize:*``, ``stmt:*``)."""
    key = (idempotency_key or "").strip()
    if not key:
        raise ApiError(400, "MISSING_IDEMPOTENCY_KEY", "The Idempotency-Key header is required.")
    if len(key) > _KEY_MAX_LENGTH or not key.isascii() or not key.isprintable():
        raise ApiError(400, "INVALID_IDEMPOTENCY_KEY", "The Idempotency-Key header is invalid.")
    route = request.scope.get("route")
    template = getattr(route, "path", request.url.path)
    return f"api:{request.method} {template}:{key}"


IdempotencyKey = Annotated[str, Depends(idempotency_key)]


def client_address(request: Request) -> str:
    """Peer address only; X-Forwarded-For is deliberately not trusted."""
    return request.client.host if request.client else "unknown"


ClientAddress = Annotated[str, Depends(client_address)]


def get_throttle(request: Request) -> security.LoginThrottle:
    return request.app.state.login_throttle


ThrottleDep = Annotated[security.LoginThrottle, Depends(get_throttle)]
