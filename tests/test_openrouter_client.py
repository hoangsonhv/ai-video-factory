"""Tests for the OpenRouter HTTP client, driven by httpx MockTransport.

No network access: every request is served by an in-process transport.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

import httpx
import pytest

from ai_video_factory.infrastructure.providers.base.errors import (
    AuthenticationError,
    InvalidResponseError,
    ProviderUnavailableError,
    RateLimitError,
)
from ai_video_factory.infrastructure.providers.base.errors import (
    TimeoutError as ProviderTimeoutError,
)
from ai_video_factory.infrastructure.providers.base.models import LLMRequest
from ai_video_factory.infrastructure.providers.openrouter.client import (
    RealOpenRouterClient,
    build_payload,
    parse_completion,
)

BASE_URL = "https://openrouter.test/api/v1"
MODEL = "deepseek/deepseek-chat-v3"


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> RealOpenRouterClient:
    return RealOpenRouterClient(
        api_key="test-key",
        base_url=BASE_URL,
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )


def _completion(content: str = '{"scenes":[]}') -> dict:
    return {
        "id": "gen-1",
        "model": MODEL,
        "choices": [
            {"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200},
    }


# --- payload building (pure) -----------------------------------------------


def test_the_payload_is_openai_shaped() -> None:
    payload = build_payload(LLMRequest(user_prompt="plan the shots"), model=MODEL)

    assert payload["model"] == MODEL
    assert payload["messages"] == [{"role": "user", "content": "plan the shots"}]
    assert payload["max_tokens"] == 1024


def test_a_system_prompt_becomes_a_system_message() -> None:
    payload = build_payload(
        LLMRequest(user_prompt="plan", system_prompt="you are a director"), model=MODEL
    )

    assert payload["messages"][0] == {"role": "system", "content": "you are a director"}
    assert payload["messages"][1]["role"] == "user"


def test_json_mode_requests_a_json_object() -> None:
    payload = build_payload(LLMRequest(user_prompt="plan", json_mode=True), model=MODEL)

    assert payload["response_format"] == {"type": "json_object"}


def test_plain_mode_sets_no_response_format() -> None:
    assert "response_format" not in build_payload(LLMRequest(user_prompt="plan"), model=MODEL)


def test_sampling_parameters_are_forwarded() -> None:
    payload = build_payload(
        LLMRequest(user_prompt="plan", temperature=0.2, top_p=0.5, max_tokens=4096), model=MODEL
    )

    assert payload["temperature"] == 0.2
    assert payload["top_p"] == 0.5
    assert payload["max_tokens"] == 4096


# --- response parsing ------------------------------------------------------


def test_a_completion_is_normalized() -> None:
    raw = parse_completion(_completion("hello"), model=MODEL)

    assert raw.content == "hello"
    assert raw.finish_reason == "stop"
    assert (raw.prompt_tokens, raw.completion_tokens, raw.total_tokens) == (120, 80, 200)


def test_a_missing_total_is_derived_from_the_parts() -> None:
    payload = _completion()
    payload["usage"] = {"prompt_tokens": 10, "completion_tokens": 5}

    assert parse_completion(payload, model=MODEL).total_tokens == 15


def test_absent_usage_is_tolerated() -> None:
    payload = _completion()
    del payload["usage"]

    assert parse_completion(payload, model=MODEL).total_tokens == 0


def test_an_api_error_object_is_surfaced() -> None:
    with pytest.raises(InvalidResponseError, match="no credits"):
        parse_completion({"error": {"message": "no credits"}}, model=MODEL)


def test_a_response_without_choices_is_rejected() -> None:
    with pytest.raises(InvalidResponseError, match="no choices"):
        parse_completion({"choices": []}, model=MODEL)


def test_an_empty_completion_is_rejected() -> None:
    with pytest.raises(InvalidResponseError, match="empty completion"):
        parse_completion(_completion("   "), model=MODEL)


def test_a_non_object_response_is_rejected() -> None:
    with pytest.raises(InvalidResponseError, match="non-object"):
        parse_completion(["nope"], model=MODEL)


# --- HTTP behaviour --------------------------------------------------------


def test_complete_posts_to_chat_completions() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["method"] = request.method
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion("planned"))

    raw = asyncio.run(_client(handler).complete(LLMRequest(user_prompt="plan"), model=MODEL))

    assert seen["url"] == f"{BASE_URL}/chat/completions"
    assert seen["method"] == "POST"
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["model"] == MODEL  # type: ignore[index]
    assert raw.content == "planned"


def test_attribution_headers_are_sent() -> None:
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["referer"] = request.headers.get("HTTP-Referer")
        seen["title"] = request.headers.get("X-Title")
        return httpx.Response(200, json=_completion())

    asyncio.run(_client(handler).complete(LLMRequest(user_prompt="plan"), model=MODEL))

    assert seen["referer"]
    assert seen["title"] == "AI Video Factory"


def test_list_models_reads_the_data_array() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models")
        return httpx.Response(200, json={"data": [{"id": MODEL}, {"id": "openai/gpt-4o"}]})

    assert asyncio.run(_client(handler).list_models()) == [MODEL, "openai/gpt-4o"]


def test_list_models_tolerates_an_unexpected_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": "not-a-list"})

    assert asyncio.run(_client(handler).list_models()) == []


# --- error translation -----------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (429, RateLimitError),
        (500, ProviderUnavailableError),
        (502, ProviderUnavailableError),
        (503, ProviderUnavailableError),
        (504, ProviderUnavailableError),
        (400, InvalidResponseError),
    ],
)
def test_http_errors_map_to_the_provider_hierarchy(status: int, expected: type) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"message": "nope"}})

    with pytest.raises(expected):
        asyncio.run(_client(handler).complete(LLMRequest(user_prompt="plan"), model=MODEL))


def test_the_api_error_message_is_surfaced() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"error": {"message": "insufficient credits"}})

    with pytest.raises(InvalidResponseError, match="insufficient credits"):
        asyncio.run(_client(handler).complete(LLMRequest(user_prompt="plan"), model=MODEL))


def test_a_transport_timeout_becomes_a_provider_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow")

    with pytest.raises(ProviderTimeoutError, match="timed out"):
        asyncio.run(_client(handler).complete(LLMRequest(user_prompt="plan"), model=MODEL))


def test_a_transport_failure_becomes_provider_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    with pytest.raises(ProviderUnavailableError, match="request failed"):
        asyncio.run(_client(handler).complete(LLMRequest(user_prompt="plan"), model=MODEL))


def test_invalid_json_is_translated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>not json</html>")

    with pytest.raises(InvalidResponseError, match="invalid JSON"):
        asyncio.run(_client(handler).complete(LLMRequest(user_prompt="plan"), model=MODEL))
