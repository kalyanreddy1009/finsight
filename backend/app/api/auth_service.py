"""Owner credential, browser sessions (devices rows) and their audit trail."""

import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta

from app.api.errors import ApiError
from app.core import security
from app.database.session import transaction

WEB_PLATFORM = "WEB_ADMIN"
_NO_KEY = "NONE"


def to_iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def invalid_refresh() -> ApiError:
    return ApiError(401, "INVALID_REFRESH_TOKEN", "Session expired. Please sign in again.")


def is_configured(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM owner_credentials WHERE id = 1").fetchone() is not None


def get_password_hash(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT password_hash FROM owner_credentials WHERE id = 1").fetchone()
    return row["password_hash"] if row else None


def create_owner(conn: sqlite3.Connection, password: str, device_name: str, now: datetime) -> tuple[str, str]:
    """Store the owner credential (once) and open the first session; returns (device_id, refresh)."""
    if is_configured(conn):
        raise ApiError(409, "ALREADY_CONFIGURED", "FinSight is already set up.")
    password_hash = security.hash_password(password)
    with transaction(conn):
        if is_configured(conn):
            raise ApiError(409, "ALREADY_CONFIGURED", "FinSight is already set up.")
        conn.execute(
            "INSERT INTO owner_credentials (id, password_hash, updated_at) VALUES (1, ?, ?)",
            (password_hash, to_iso(now)),
        )
        return create_session(conn, device_name, now)


def _audit(
    conn: sqlite3.Connection, event_type: str, actor_id: str | None, device_id: str, metadata: dict[str, str]
) -> None:
    conn.execute(
        "INSERT INTO audit_events (id, event_type, actor_device_id, target_object_type, target_object_id, "
        "metadata_json, created_at) VALUES (?, ?, ?, 'DEVICE', ?, ?, ?)",
        (str(uuid.uuid4()), event_type, actor_id, device_id, json.dumps(metadata), metadata["at"]),
    )


def _new_refresh_token(device_id: str) -> str:
    # The device id prefix lets a replayed (already rotated) token be traced to its device.
    return f"{device_id}.{security.new_refresh_token()}"


def create_session(conn: sqlite3.Connection, device_name: str, now: datetime) -> tuple[str, str]:
    device_id = str(uuid.uuid4())
    refresh = _new_refresh_token(device_id)
    stamp = to_iso(now)
    with transaction(conn):
        conn.execute(
            "INSERT INTO devices (id, device_name, platform, public_key_pem, refresh_token_hash, "
            "created_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                device_id,
                device_name,
                WEB_PLATFORM,
                _NO_KEY,
                security.hash_refresh_token(refresh),
                stamp,
                stamp,
            ),
        )
        _audit(conn, "DEVICE_LOGIN", device_id, device_id, {"device_name": device_name, "at": stamp})
    return device_id, refresh


def find_active_device(conn: sqlite3.Connection, device_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM devices WHERE id = ? AND is_revoked = 0", (device_id,)).fetchone()


def revoke_device(
    conn: sqlite3.Connection, device_id: str, actor_id: str | None, now: datetime, reason: str
) -> bool:
    """Revoke a device; returns False if it does not exist. Already revoked devices are left as-is."""
    with transaction(conn):
        row = conn.execute("SELECT is_revoked FROM devices WHERE id = ?", (device_id,)).fetchone()
        if row is None:
            return False
        if not row["is_revoked"]:
            conn.execute("UPDATE devices SET is_revoked = 1 WHERE id = ?", (device_id,))
            _audit(conn, "DEVICE_REVOKED", actor_id, device_id, {"reason": reason, "at": to_iso(now)})
    return True


def rotate_refresh(conn: sqlite3.Connection, presented: str, now: datetime) -> tuple[str, str]:
    """Validate and rotate a refresh token; a stale (reused) token revokes its device."""
    device_id, _, secret = presented.partition(".")
    if not secret:
        raise invalid_refresh()
    with transaction(conn):
        device = find_active_device(conn, device_id)
        if device is None:
            raise invalid_refresh()
        if not security.tokens_match(presented, device["refresh_token_hash"]):
            revoke_device(conn, device_id, device_id, now, "REFRESH_TOKEN_REUSE")
            reused = True
        else:
            reused = False
    if reused:
        raise invalid_refresh()
    idle_limit = timedelta(seconds=security.REFRESH_TOKEN_TTL_SECONDS)
    if now - datetime.fromisoformat(device["last_seen_at"]) > idle_limit:
        raise invalid_refresh()
    replacement = _new_refresh_token(device_id)
    cursor = conn.execute(
        "UPDATE devices SET refresh_token_hash = ?, last_seen_at = ? "
        "WHERE id = ? AND refresh_token_hash = ? AND is_revoked = 0",
        (security.hash_refresh_token(replacement), to_iso(now), device_id, device["refresh_token_hash"]),
    )
    if cursor.rowcount != 1:
        raise invalid_refresh()
    return device_id, replacement


def list_devices(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, device_name, platform, created_at, last_seen_at, is_revoked FROM devices "
        "ORDER BY created_at DESC, id"
    ).fetchall()
