"""Tests for the exponential-backoff retry policy."""

from __future__ import annotations

import asyncio

import pytest

from ai_video_factory.infrastructure.providers.base.errors import (
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
)
from ai_video_factory.infrastructure.providers.base.retry import RetryPolicy


class _Counter:
    def __init__(self) -> None:
        self.calls = 0
        self.delays: list[float] = []

    async def sleep(self, delay: float) -> None:
        self.delays.append(delay)


def test_succeeds_without_retry() -> None:
    counter = _Counter()
    policy = RetryPolicy(max_retries=3, sleep=counter.sleep)

    async def operation() -> str:
        counter.calls += 1
        return "ok"

    assert asyncio.run(policy.run(operation)) == "ok"
    assert counter.calls == 1
    assert counter.delays == []


def test_retries_then_succeeds() -> None:
    counter = _Counter()
    policy = RetryPolicy(max_retries=3, base_delay=0.1, sleep=counter.sleep)

    async def operation() -> str:
        counter.calls += 1
        if counter.calls < 3:
            raise RateLimitError("429")
        return "ok"

    assert asyncio.run(policy.run(operation)) == "ok"
    assert counter.calls == 3
    assert counter.delays == [0.1, 0.2]  # exponential backoff


def test_exhausts_retries_and_raises() -> None:
    counter = _Counter()
    policy = RetryPolicy(max_retries=2, base_delay=0.1, sleep=counter.sleep)

    async def operation() -> str:
        counter.calls += 1
        raise ProviderUnavailableError("503")

    with pytest.raises(ProviderUnavailableError):
        asyncio.run(policy.run(operation))
    assert counter.calls == 3  # initial + 2 retries


def test_timeout_is_retryable() -> None:
    counter = _Counter()
    policy = RetryPolicy(max_retries=1, base_delay=0.0, sleep=counter.sleep)

    async def operation() -> str:
        counter.calls += 1
        if counter.calls == 1:
            raise TimeoutError("slow")
        return "ok"

    assert asyncio.run(policy.run(operation)) == "ok"
    assert counter.calls == 2


def test_non_retryable_error_is_not_retried() -> None:
    counter = _Counter()
    policy = RetryPolicy(max_retries=3, sleep=counter.sleep)

    async def operation() -> str:
        counter.calls += 1
        raise AuthenticationError("401")

    with pytest.raises(AuthenticationError):
        asyncio.run(policy.run(operation))
    assert counter.calls == 1
