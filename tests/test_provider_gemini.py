"""Tests for GeminiProvider using a fake client (no SDK, no network)."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from ai_video_factory.infrastructure.config.settings import ProviderSettings
from ai_video_factory.infrastructure.providers.base.errors import (
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
)
from ai_video_factory.infrastructure.providers.base.models import LLMRequest, RawCompletion
from ai_video_factory.infrastructure.providers.gemini.provider import GeminiProvider
from ai_video_factory.shared.health import HealthStatus


class FakeGeminiClient:
    """In-memory GeminiClient double satisfying the client protocol."""

    def __init__(
        self,
        *,
        completion: RawCompletion | None = None,
        error: Exception | None = None,
        models: list[str] | None = None,
        token_count: int = 7,
        fail_times: int = 0,
        delay: float = 0.0,
    ) -> None:
        self._completion = completion
        self._error = error
        self._models = models if models is not None else ["gemini-2.0-flash"]
        self._token_count = token_count
        self._fail_times = fail_times
        self._delay = delay
        self.complete_calls = 0

    async def complete(self, request: LLMRequest, *, model: str) -> RawCompletion:
        self.complete_calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._fail_times > 0:
            self._fail_times -= 1
            raise RateLimitError("429")
        if self._error is not None:
            raise self._error
        return self._completion or RawCompletion(
            content="hi", finish_reason="STOP", prompt_tokens=3, completion_tokens=2, total_tokens=5
        )

    async def count_tokens(self, text: str, *, model: str) -> int:
        return self._token_count

    async def list_models(self) -> list[str]:
        if self._error is not None:
            raise self._error
        return self._models


def _clock(values: list[float]) -> object:
    iterator: Iterator[float] = iter(values)
    return lambda: next(iterator)


def _settings(**overrides: object) -> ProviderSettings:
    base: dict[str, object] = {"retry_count": 0, "timeout": 5.0}
    base.update(overrides)
    return ProviderSettings(**base)


def test_generate_maps_completion_to_response() -> None:
    client = FakeGeminiClient(
        completion=RawCompletion(
            content="a story",
            finish_reason="STOP",
            prompt_tokens=11,
            completion_tokens=4,
            total_tokens=15,
        )
    )
    provider = GeminiProvider(_settings(), client=client, clock=_clock([1.0, 1.5]))  # type: ignore[arg-type]

    response = asyncio.run(provider.generate(LLMRequest(user_prompt="write")))

    assert response.content == "a story"
    assert response.finish_reason == "STOP"
    assert response.provider == "gemini"
    assert response.model == "gemini-3.5-flash"
    assert response.latency == pytest.approx(0.5)
    assert response.usage.total_tokens == 15


def test_generate_without_api_key_raises_authentication_error() -> None:
    provider = GeminiProvider(_settings())  # no client, no api key
    with pytest.raises(AuthenticationError):
        asyncio.run(provider.generate(LLMRequest(user_prompt="x")))


def test_generate_propagates_non_retryable_error() -> None:
    client = FakeGeminiClient(error=AuthenticationError("401"))
    provider = GeminiProvider(_settings(retry_count=3), client=client)
    with pytest.raises(AuthenticationError):
        asyncio.run(provider.generate(LLMRequest(user_prompt="x")))
    assert client.complete_calls == 1


def test_generate_times_out() -> None:
    client = FakeGeminiClient(delay=1.0)
    provider = GeminiProvider(_settings(retry_count=0, timeout=0.01), client=client)
    with pytest.raises(TimeoutError):
        asyncio.run(provider.generate(LLMRequest(user_prompt="x")))


def test_generate_retries_transient_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    client = FakeGeminiClient(fail_times=2)
    provider = GeminiProvider(_settings(retry_count=3), client=client)

    response = asyncio.run(provider.generate(LLMRequest(user_prompt="x")))
    assert response.content == "hi"
    assert client.complete_calls == 3


def test_count_tokens_and_models() -> None:
    client = FakeGeminiClient(token_count=42, models=["gemini-2.0-flash", "gemini-1.5-pro"])
    provider = GeminiProvider(_settings(), client=client)
    assert asyncio.run(provider.count_tokens("hello")) == 42
    assert asyncio.run(provider.models()) == ["gemini-2.0-flash", "gemini-1.5-pro"]


def test_health_check_warn_when_no_key() -> None:
    provider = GeminiProvider(_settings())
    health = asyncio.run(provider.health_check())
    assert health.status is HealthStatus.WARN


def test_health_check_ok_when_reachable() -> None:
    provider = GeminiProvider(_settings(), client=FakeGeminiClient())
    health = asyncio.run(provider.health_check())
    assert health.status is HealthStatus.OK


def test_health_check_fail_when_unreachable() -> None:
    client = FakeGeminiClient(error=ProviderUnavailableError("503"))
    provider = GeminiProvider(_settings(), client=client)
    health = asyncio.run(provider.health_check())
    assert health.status is HealthStatus.FAIL
