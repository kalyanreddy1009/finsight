"""API error type and the exception handlers that render every failure as an envelope."""

import logging
import sqlite3
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.envelope import fail
from app.finance.ledger_service import IdempotencyConflictError

logger = logging.getLogger("finsight.api")

_STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
}


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        meta: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.meta = meta
        self.headers = headers


def not_found(what: str) -> ApiError:
    return ApiError(404, "NOT_FOUND", f"{what} not found.")


def unauthorized(message: str = "Authentication required.") -> ApiError:
    return ApiError(401, "UNAUTHORIZED", message, headers={"WWW-Authenticate": "Bearer"})


def _respond(
    status: int,
    code: str,
    message: str,
    meta: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(fail(code, message, meta), status_code=status, headers=headers)


async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
    return _respond(exc.status_code, exc.code, exc.message, exc.meta, exc.headers)


async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _STATUS_CODES.get(exc.status_code, "HTTP_ERROR")
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return _respond(exc.status_code, code, message, headers=dict(exc.headers or {}) or None)


async def _request_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    parts = []
    for err in exc.errors()[:5]:
        location = ".".join(str(p) for p in err["loc"] if p not in ("body", "query", "header"))
        parts.append(f"{location}: {err['msg']}" if location else err["msg"])
    return _respond(422, "VALIDATION_ERROR", "; ".join(parts) or "Invalid request.")


_DOMAIN_MODULE_PREFIXES = ("app.finance.", "app.ingestion.")
_GENERIC_VALIDATION_MESSAGE = "The request could not be processed."


def _raised_by_domain_code(exc: BaseException) -> bool:
    """True when the innermost Python frame of the traceback is ledger/chart/ingestion code."""
    tb = exc.__traceback__
    if tb is None:
        return False
    while tb.tb_next is not None:
        tb = tb.tb_next
    module = tb.tb_frame.f_globals.get("__name__", "")
    return module.startswith(_DOMAIN_MODULE_PREFIXES)


async def _idempotency_conflict(_: Request, exc: IdempotencyConflictError) -> JSONResponse:
    return _respond(
        409, "IDEMPOTENCY_KEY_REUSED", "This Idempotency-Key was already used for a different request."
    )


async def _value_error(_: Request, exc: ValueError) -> JSONResponse:
    """Domain ValueErrors carry user-safe messages ('Unknown ...' = missing referenced id).

    A ValueError from anywhere else (parsing libraries, framework code) gets a fixed message.
    """
    if not _raised_by_domain_code(exc):
        logger.warning("Unmapped ValueError: %s", exc)
        return _respond(422, "VALIDATION_ERROR", _GENERIC_VALIDATION_MESSAGE)
    message = str(exc) or _GENERIC_VALIDATION_MESSAGE
    if message.startswith("Unknown"):
        return _respond(404, "NOT_FOUND", message)
    return _respond(422, "VALIDATION_ERROR", message)


async def _type_error(_: Request, exc: TypeError) -> JSONResponse:
    logger.warning("Type error from a service call: %s", exc)
    return _respond(422, "VALIDATION_ERROR", "Invalid request.")


async def _integrity_error(_: Request, exc: sqlite3.IntegrityError) -> JSONResponse:
    logger.warning("Integrity error: %s", exc)
    return _respond(422, "VALIDATION_ERROR", "The request violates a data constraint.")


async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error", exc_info=exc)
    return _respond(500, "INTERNAL_ERROR", "An unexpected error occurred.")


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _request_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(IdempotencyConflictError, _idempotency_conflict)  # type: ignore[arg-type]
    app.add_exception_handler(ValueError, _value_error)  # type: ignore[arg-type]
    app.add_exception_handler(TypeError, _type_error)  # type: ignore[arg-type]
    app.add_exception_handler(sqlite3.IntegrityError, _integrity_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unexpected)
