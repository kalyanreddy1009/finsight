import asyncio
import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.ai import ollama_provider as ollama

URL = "http://127.0.0.1:11434"


def provider_for(
    handler: Callable[[httpx.Request], httpx.Response], url: str = URL, model: str = "llama3.2:3b"
) -> tuple[ollama.OllamaProvider, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(recording))
    return ollama.OllamaProvider(url, model, 30, client=client), seen


def chat_reply(text: str = "hello") -> httpx.Response:
    return httpx.Response(200, json={"message": {"role": "assistant", "content": text}})


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:11434",
        "http://127.5.6.7:11434",
        "https://localhost:11434",
        "http://LOCALHOST:11434/",
        "http://[::1]:11434",
    ],
)
def test_loopback_urls_are_local(url: str) -> None:
    assert ollama.is_local_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com:11434",
        "http://192.168.1.10:11434",
        "http://10.0.0.1",
        "http://0.0.0.0:11434",
        "http://localhost.evil.com",
        "http://127.0.0.1@evil.com",
        "http://user:pw@127.0.0.1:11434",
        "ftp://127.0.0.1",
        "file:///etc/passwd",
        "127.0.0.1:11434",
        "",
        "http://[::ffff:8.8.8.8]",
        "http://127.0.0.1:notaport",
    ],
)
def test_non_loopback_urls_are_refused(url: str) -> None:
    assert not ollama.is_local_url(url)


def test_model_installed_matches_latest_tag() -> None:
    assert ollama.model_installed("llama3.2:3b", ["llama3.2:3b"])
    assert ollama.model_installed("llama3", ["llama3:latest"])
    assert not ollama.model_installed("llama3.2:3b", ["llama3.2:1b"])


def test_status_lists_models() -> None:
    handler = lambda _: httpx.Response(200, json={"models": [{"name": "a:1"}, {"name": "b:2"}, {"x": 1}]})  # noqa: E731
    provider, seen = provider_for(handler)
    result = asyncio.run(provider.status())
    assert result == ollama.OllamaStatus(reachable=True, models=["a:1", "b:2"])
    assert seen[0].method == "GET"
    assert str(seen[0].url) == f"{URL}/api/tags"


def test_status_is_not_reachable_when_connection_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    provider, _ = provider_for(handler)
    assert asyncio.run(provider.status()) == ollama.OllamaStatus(reachable=False, models=[])


def test_status_non_local_raises_without_sending() -> None:
    provider, seen = provider_for(lambda _: chat_reply(), url="http://example.com")
    with pytest.raises(ollama.OllamaError) as caught:
        asyncio.run(provider.status())
    assert caught.value.kind == ollama.NOT_LOCAL
    assert seen == []


def test_chat_request_shape_and_schema_format() -> None:
    provider, seen = provider_for(lambda _: chat_reply("hi there"))
    messages = [{"role": "user", "content": "q"}]
    assert asyncio.run(provider.chat(messages)) == "hi there"
    body: dict[str, Any] = json.loads(seen[0].content)
    assert body == {
        "model": "llama3.2:3b",
        "messages": messages,
        "stream": False,
        "keep_alive": "2m",
        "options": {"temperature": 0.2, "num_ctx": 4096},
    }
    assert str(seen[0].url) == f"{URL}/api/chat"
    schema = {"type": "object"}
    asyncio.run(provider.chat(messages, schema))
    assert json.loads(seen[1].content)["format"] == schema


def error_kind(provider: ollama.OllamaProvider) -> str:
    with pytest.raises(ollama.OllamaError) as caught:
        asyncio.run(provider.chat([{"role": "user", "content": "q"}]))
    return caught.value.kind


def test_chat_error_mapping() -> None:
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    def connect_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.RemoteProtocolError("bad", request=request)

    cases: list[tuple[Callable[[httpx.Request], httpx.Response], str]] = [
        (refused, ollama.UNREACHABLE),
        (connect_timeout, ollama.UNREACHABLE),
        (slow, ollama.TIMEOUT),
        (broken, ollama.PROVIDER_ERROR),
        (lambda _: httpx.Response(404, json={"error": "model not found"}), ollama.MODEL_MISSING),
        (lambda _: httpx.Response(500, text="boom"), ollama.PROVIDER_ERROR),
        (lambda _: httpx.Response(302, headers={"location": "http://evil.example/"}), ollama.PROVIDER_ERROR),
        (lambda _: httpx.Response(200, text="not json"), ollama.INVALID_RESPONSE),
        (lambda _: httpx.Response(200, json={"message": {"content": 5}}), ollama.INVALID_RESPONSE),
        (lambda _: httpx.Response(200, json=["x"]), ollama.INVALID_RESPONSE),
    ]
    for handler, kind in cases:
        provider, _ = provider_for(handler)
        assert error_kind(provider) == kind


def test_redirect_is_not_followed() -> None:
    provider, seen = provider_for(lambda _: httpx.Response(307, headers={"location": "http://evil.example/"}))
    assert error_kind(provider) == ollama.PROVIDER_ERROR
    assert len(seen) == 1


def test_oversized_response_is_rejected() -> None:
    big = "x" * (ollama.MAX_RESPONSE_BYTES + 1)
    provider, _ = provider_for(lambda _: chat_reply(big))
    assert error_kind(provider) == ollama.INVALID_RESPONSE


def test_chat_non_local_raises_without_sending() -> None:
    provider, seen = provider_for(lambda _: chat_reply(), url="http://8.8.8.8:11434")
    assert error_kind(provider) == ollama.NOT_LOCAL
    assert seen == []


def slow_provider(timeout: float) -> ollama.OllamaProvider:
    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(5)
        return chat_reply()

    client = httpx.AsyncClient(transport=httpx.MockTransport(slow))
    return ollama.OllamaProvider(URL, "m", timeout, client=client)


def test_chat_has_a_total_deadline() -> None:
    assert error_kind(slow_provider(0.1)) == ollama.TIMEOUT


def test_status_slow_server_counts_as_not_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ollama, "STATUS_TIMEOUT_SECONDS", 0.1)
    result = asyncio.run(slow_provider(30).status())
    assert result == ollama.OllamaStatus(reachable=False, models=[])
