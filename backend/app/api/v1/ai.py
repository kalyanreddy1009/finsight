"""Local-only AI assistant endpoints (Ollama on loopback). Read-only: nothing here writes the ledger."""

import asyncio
import logging
import sqlite3
import time
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from app.ai import assistant
from app.ai import ollama_provider as ollama
from app.ai.privacy_filter import DEFAULT_DISCLAIMER, AIInsightResponseSchema
from app.api.deps import ClockDep, Conn, DeviceId, SettingsDep
from app.api.envelope import ok
from app.api.errors import ApiError
from app.api.v1.schemas import ChatIn

logger = logging.getLogger("finsight.api")
router = APIRouter(prefix="/ai", tags=["ai"])

# One AI request at a time; a second caller is refused rather than queued.
AI_LOCK = asyncio.Lock()

_ERRORS: dict[str, tuple[int, str, str]] = {
    ollama.UNREACHABLE: (503, "AI_UNAVAILABLE", "The local AI is not running. Start Ollama, then try again."),
    ollama.MODEL_MISSING: (
        503,
        "AI_MODEL_MISSING",
        "The AI model is not installed. Pull the model in Ollama, then try again.",
    ),
    ollama.NOT_LOCAL: (
        503,
        "AI_NOT_LOCAL",
        "The AI address is not on this computer. Point the Ollama URL at localhost to use the assistant.",
    ),
    ollama.TIMEOUT: (504, "AI_TIMEOUT", "The local AI took too long to answer. Try again in a moment."),
    ollama.PROVIDER_ERROR: (
        502,
        "AI_PROVIDER_ERROR",
        "The local AI reported an error. Check that Ollama is healthy, then try again.",
    ),
    ollama.INVALID_RESPONSE: (
        502,
        "AI_INVALID_RESPONSE",
        "The local AI sent an answer that could not be used. Try again.",
    ),
}
_BUSY = ApiError(429, "AI_BUSY", "The AI is busy with another request. Wait a moment, then try again.")


def get_ollama_provider(settings: SettingsDep) -> ollama.OllamaProvider:
    """Overridable in tests (``app.dependency_overrides``) to inject a mock transport."""
    return ollama.OllamaProvider(settings.ollama_url, settings.ollama_model, settings.ai_timeout_seconds)


Provider = Annotated[ollama.OllamaProvider, Depends(get_ollama_provider)]


def _api_error(kind: str) -> ApiError:
    status, code, message = _ERRORS[kind]
    return ApiError(status, code, message)


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


@router.get("/status")
async def status(provider: Provider, _: DeviceId) -> dict:
    try:
        result = await provider.status()
    except ollama.OllamaError as exc:
        raise _api_error(exc.kind) from None
    return ok(
        {
            "provider": assistant.PROVIDER,
            "reachable": result.reachable,
            "model": provider.model,
            "model_available": result.reachable and ollama.model_installed(provider.model, result.models),
            "installed_models": result.models,
            "local_only": True,
        }
    )


@router.post("/chat")
async def chat(body: ChatIn, conn: Conn, clock: ClockDep, provider: Provider, _: DeviceId) -> dict:
    _guard(provider)
    async with _exclusive():
        facts = assistant.build_facts(conn, clock().date())
        digest = assistant.facts_hash(facts)
        history = [m.model_dump() for m in body.history]
        messages = assistant.chat_messages(facts, body.question, history)
        started = time.monotonic()
        try:
            answer = (await provider.chat(messages)).strip()
            if not answer:
                raise ollama.OllamaError(ollama.INVALID_RESPONSE)
        except ollama.OllamaError as exc:
            _audit_failure(conn, "CHAT", digest, exc, started)
            raise _api_error(exc.kind) from None
        except BaseException:
            _audit_unexpected(conn, "CHAT", digest, started)
            raise
        latency = _elapsed_ms(started)
        assistant.record_request(conn, "CHAT", digest, "COMPLETED", latency)
    return ok({"answer": answer, "model": provider.model, "latency_ms": latency, "facts": facts})


@router.post("/insight")
async def insight(conn: Conn, clock: ClockDep, provider: Provider, _: DeviceId) -> dict:
    _guard(provider)
    today = clock().date()
    async with _exclusive():
        facts = assistant.build_facts(conn, today)
        digest = assistant.facts_hash(facts)
        schema = AIInsightResponseSchema.model_json_schema()
        started = time.monotonic()
        try:
            raw = await provider.chat(assistant.insight_messages(facts), schema)
            parsed = AIInsightResponseSchema.model_validate_json(raw)
        except ValidationError:
            _audit_failure(conn, "INSIGHT", digest, ollama.OllamaError(ollama.INVALID_RESPONSE), started)
            raise _api_error(ollama.INVALID_RESPONSE) from None
        except ollama.OllamaError as exc:
            _audit_failure(conn, "INSIGHT", digest, exc, started)
            raise _api_error(exc.kind) from None
        except BaseException:
            _audit_unexpected(conn, "INSIGHT", digest, started)
            raise
        latency = _elapsed_ms(started)
        result = parsed.model_copy(update={"disclaimer": DEFAULT_DISCLAIMER}).model_dump()
        assistant.record_insight(conn, digest, latency, today, result)
    return ok({"insight": result, "model": provider.model, "latency_ms": latency})


def _guard(provider: ollama.OllamaProvider) -> None:
    try:
        provider.ensure_local()
    except ollama.OllamaError as exc:
        raise _api_error(exc.kind) from None


class _exclusive:  # noqa: N801 - used as a context manager
    async def __aenter__(self) -> None:
        if AI_LOCK.locked():
            raise _BUSY
        await AI_LOCK.acquire()

    async def __aexit__(self, *exc_info: object) -> None:
        AI_LOCK.release()


def _audit_failure(
    conn: sqlite3.Connection, purpose: str, digest: str, exc: ollama.OllamaError, started: float
) -> None:
    outcome = "VALIDATION_FAILED" if exc.kind == ollama.INVALID_RESPONSE else "PROVIDER_ERROR"
    assistant.record_request(conn, purpose, digest, outcome, _elapsed_ms(started))


def _audit_unexpected(conn: sqlite3.Connection, purpose: str, digest: str, started: float) -> None:
    """Best-effort PROVIDER_ERROR row for an unexpected exit (including cancellation); never masks it."""
    try:
        assistant.record_request(conn, purpose, digest, "PROVIDER_ERROR", _elapsed_ms(started))
    except Exception:  # noqa: BLE001 - the original exception is re-raised by the caller
        logger.warning("Could not write the AI audit row.")
