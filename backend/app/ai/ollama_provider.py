"""Small async client for a local Ollama server. Loopback only; no redirects; capped responses."""

import asyncio
import ipaddress
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

STATUS_TIMEOUT_SECONDS = 2.0
MAX_RESPONSE_BYTES = 64 * 1024
KEEP_ALIVE = "2m"
TEMPERATURE = 0.2
NUM_CTX = 4096

UNREACHABLE = "UNREACHABLE"
MODEL_MISSING = "MODEL_MISSING"
TIMEOUT = "TIMEOUT"
PROVIDER_ERROR = "PROVIDER_ERROR"
INVALID_RESPONSE = "INVALID_RESPONSE"
NOT_LOCAL = "NOT_LOCAL"


class OllamaError(Exception):
    """Failure talking to Ollama; ``kind`` is one of the module constants above."""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


@dataclass(frozen=True)
class OllamaStatus:
    reachable: bool
    models: list[str]


def is_local_url(url: str) -> bool:
    """True only for an http(s) URL whose host is localhost or a loopback IP, with no credentials."""
    try:
        parts = urlsplit(url)
        host = parts.hostname
        parts.port  # noqa: B018 - raises ValueError on a malformed port
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not host or parts.username or parts.password:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def model_installed(model: str, installed: list[str]) -> bool:
    names = set(installed)
    return model in names or (":" not in model and f"{model}:latest" in names)


class OllamaProvider:
    def __init__(
        self, base_url: str, model: str, timeout_seconds: float, client: httpx.AsyncClient | None = None
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._client = client

    def ensure_local(self) -> None:
        if not is_local_url(self.base_url):
            raise OllamaError(NOT_LOCAL)

    async def status(self) -> OllamaStatus:
        """Reachability and installed model names. Only a non-local URL raises."""
        self.ensure_local()
        try:
            data = await self._request("GET", "/api/tags", None, STATUS_TIMEOUT_SECONDS)
        except OllamaError as exc:
            if exc.kind == NOT_LOCAL:
                raise
            return OllamaStatus(reachable=False, models=[])
        models = data.get("models") if isinstance(data, dict) else None
        names = (
            [m["name"] for m in models if isinstance(m, dict) and isinstance(m.get("name"), str)]
            if isinstance(models, list)
            else []
        )
        return OllamaStatus(reachable=True, models=names)

    async def chat(self, messages: list[dict[str, str]], json_schema: dict[str, Any] | None = None) -> str:
        self.ensure_local()
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": KEEP_ALIVE,
            "options": {"temperature": TEMPERATURE, "num_ctx": NUM_CTX},
        }
        if json_schema is not None:
            payload["format"] = json_schema
        data = await self._request("POST", "/api/chat", payload, self.timeout_seconds)
        message = data.get("message") if isinstance(data, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise OllamaError(INVALID_RESPONSE)
        return content

    async def _request(self, method: str, path: str, payload: dict[str, Any] | None, timeout: float) -> Any:
        """One request under a total deadline (httpx timeouts alone are per operation)."""
        try:
            async with asyncio.timeout(timeout):
                if self._client is not None:
                    return await self._send(self._client, method, path, payload, timeout)
                async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as client:
                    return await self._send(client, method, path, payload, timeout)
        except TimeoutError:
            raise OllamaError(TIMEOUT) from None

    async def _send(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        timeout: float,
    ) -> Any:
        try:
            async with client.stream(
                method, self.base_url + path, json=payload, timeout=timeout, follow_redirects=False
            ) as response:
                if response.status_code == 404 and path == "/api/chat":
                    raise OllamaError(MODEL_MISSING)
                if response.status_code != 200:
                    raise OllamaError(PROVIDER_ERROR)
                body = await _read_capped(response)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise OllamaError(UNREACHABLE) from None
        except httpx.TimeoutException:
            raise OllamaError(TIMEOUT) from None
        except httpx.HTTPError:
            raise OllamaError(PROVIDER_ERROR) from None
        try:
            return json.loads(body)
        except ValueError:
            raise OllamaError(INVALID_RESPONSE) from None


async def _read_capped(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            raise OllamaError(INVALID_RESPONSE)
        chunks.append(chunk)
    return b"".join(chunks)
