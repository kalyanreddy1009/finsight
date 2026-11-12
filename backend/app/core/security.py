"""Password hashing, access tokens, refresh tokens and login throttling."""

import hashlib
import hmac
import secrets
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

import anyio.to_thread
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

ACCESS_TOKEN_TTL_SECONDS = 15 * 60
REFRESH_TOKEN_TTL_SECONDS = 30 * 24 * 3600
MIN_PASSWORD_LENGTH = 12
MIN_SECRET_BYTES = 32
MAX_FAILED_LOGINS = 5
THROTTLE_WINDOW_SECONDS = 15 * 60
GLOBAL_FAILED_LOGIN_CEILING = 50
REFRESH_REUSE_GRACE_SECONDS = 30
ABSOLUTE_SESSION_LIFETIME_SECONDS = 90 * 24 * 3600
_ALGORITHM = "HS256"

_hasher = PasswordHasher()
# Verified against when no credential exists, so timing does not reveal the configured state.
_DUMMY_HASH = _hasher.hash("finsight-dummy-password")


class TokenError(Exception):
    """The access token is missing, malformed, expired or otherwise invalid."""


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def validate_jwt_secret(secret: str | None) -> str:
    if secret is None or len(secret.encode("utf-8")) < MIN_SECRET_BYTES:
        raise RuntimeError(
            f"FINSIGHT_JWT_SECRET must be set to at least {MIN_SECRET_BYTES} bytes to start the API."
        )
    return secret


def create_access_token(device_id: str, secret: str, now: float | None = None) -> str:
    issued = int(now if now is not None else time.time())
    claims = {"sub": device_id, "jti": str(uuid.uuid4()), "exp": issued + ACCESS_TOKEN_TTL_SECONDS}
    return jwt.encode(claims, secret, algorithm=_ALGORITHM)


def decode_access_token(token: str, secret: str, now: float | None = None) -> str:
    """Return the device id (sub) of a valid token. ``now`` is injectable for tests."""
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[_ALGORITHM],
            options={"require": ["sub", "jti", "exp"], "verify_exp": False},
        )
    except jwt.PyJWTError as exc:
        raise TokenError("invalid token") from exc
    current = now if now is not None else time.time()
    if not isinstance(claims["sub"], str) or claims["exp"] <= current:
        raise TokenError("invalid token")
    return claims["sub"]


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_match(presented: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_refresh_token(presented), stored_hash)


@dataclass
class LoginThrottle:
    """In-memory failed-login limiter, sliding window.

    Each client address may fail ``max_failures`` times per window; independently, all addresses
    together may fail ``global_ceiling`` times per window, after which everyone is refused.
    """

    clock: Callable[[], float] = time.time
    max_failures: int = MAX_FAILED_LOGINS
    global_ceiling: int = GLOBAL_FAILED_LOGIN_CEILING
    window_seconds: int = THROTTLE_WINDOW_SECONDS

    def __post_init__(self) -> None:
        self._failures: dict[str, deque[float]] = {}
        self._global: deque[float] = deque()

    def _prune(self, failures: deque[float]) -> deque[float]:
        cutoff = self.clock() - self.window_seconds
        while failures and failures[0] <= cutoff:
            failures.popleft()
        return failures

    def is_locked(self, key: str) -> bool:
        if len(self._prune(self._global)) >= self.global_ceiling:
            return True
        failures = self._failures.get(key)
        if failures is None:
            return False
        if not self._prune(failures):
            del self._failures[key]
            return False
        return len(failures) >= self.max_failures

    def record_failure(self, key: str) -> None:
        now = self.clock()
        self._prune(self._failures.setdefault(key, deque())).append(now)
        self._prune(self._global).append(now)

    def reset(self, key: str) -> None:
        """A successful login clears that address's failures (the global count is untouched)."""
        self._failures.pop(key, None)


async def hash_password_async(password: str) -> str:
    return await anyio.to_thread.run_sync(hash_password, password)


async def verify_password_async(password: str, password_hash: str | None) -> bool:
    return await anyio.to_thread.run_sync(verify_password, password, password_hash)
