"""Uniform JSON response envelope: {"data", "error", "meta"}."""

from typing import Any


def ok(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": meta}


def fail(code: str, message: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"data": None, "error": {"code": code, "message": message}, "meta": meta}
