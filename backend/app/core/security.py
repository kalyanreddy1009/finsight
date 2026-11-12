"""Password hashing, access tokens, refresh tokens and login throttling."""

import hashlib
import hmac
import secrets
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

ACCESS_TOKEN_TTL_SECONDS = 15 * 60
REFRESH_TOKEN_TTL_SECONDS = 30 * 24 * 3600
MIN_PASSWORD_LENGTH = 12
MIN_SECRET_BYTES = 32
MAX_FAILED_LOGINS = 5
THROTTLE_WINDOW_SECONDS = 15 * 60
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
    """In-memory failed-login limiter: 5 failures inside a sliding 15 minute window lock logins."""

    clock: Callable[[], float] = time.time
    max_failures: int = MAX_FAILED_LOGINS
    window_seconds: int = THROTTLE_WINDOW_SECONDS

    def __post_init__(self) -> None:
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str) -> deque[float]:
        failures = self._failures[key]
        cutoff = self.clock() - self.window_seconds
        while failures and failures[0] <= cutoff:
            failures.popleft()
        return failures

    def is_locked(self, key: str) -> bool:
        return len(self._prune(key)) >= self.max_failures

    def record_failure(self, key: str) -> None:
        self._prune(key).append(self.clock())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
