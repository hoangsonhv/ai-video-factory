"""Tests for the image rate limiter (concurrency, 429 backoff, display)."""

from __future__ import annotations

import asyncio

import pytest

from ai_video_factory.infrastructure.providers.base.errors import (
    ProviderUnavailableError,
    RateLimitError,
)
from ai_video_factory.infrastructure.providers.image.base.rate_limit import (
    BACKOFF_SCHEDULE,
    ImageRateLimiter,
)


class _Sleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def sleep(self, delay: float) -> None:
        self.delays.append(delay)


def test_backoff_schedule_is_2_5_10_20() -> None:
    assert BACKOFF_SCHEDULE == (2.0, 5.0, 10.0, 20.0)


def test_rate_limit_backoff_follows_schedule_and_announces() -> None:
    sleeper = _Sleeper()
    messages: list[str] = []
    limiter = ImageRateLimiter(on_rate_limit=messages.append, sleep=sleeper.sleep)
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls <= 3:
            raise RateLimitError("429")  # no Retry-After -> use the schedule
        return "ok"

    assert asyncio.run(limiter.run(operation)) == "ok"
    assert sleeper.delays == [2.0, 5.0, 10.0]  # exponential backoff, never 0s
    assert messages == [
        "Rate limit reached, waiting 2 seconds...",
        "Rate limit reached, waiting 5 seconds...",
        "Rate limit reached, waiting 10 seconds...",
    ]


def test_respects_retry_after_when_present() -> None:
    sleeper = _Sleeper()
    messages: list[str] = []
    limiter = ImageRateLimiter(on_rate_limit=messages.append, sleep=sleeper.sleep)
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RateLimitError("429", retry_after=34.0)
        return "ok"

    assert asyncio.run(limiter.run(operation)) == "ok"
    assert sleeper.delays == [34.0]  # server hint wins over the schedule
    assert messages == ["Rate limit reached, waiting 34 seconds..."]


def test_never_retries_immediately() -> None:
    sleeper = _Sleeper()
    limiter = ImageRateLimiter(sleep=sleeper.sleep)
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RateLimitError("429", retry_after=0.0)  # a zero hint is ignored
        return "ok"

    assert asyncio.run(limiter.run(operation)) == "ok"
    assert sleeper.delays == [2.0]
    assert all(delay > 0 for delay in sleeper.delays)


def test_exhausts_schedule_then_reraises() -> None:
    sleeper = _Sleeper()
    limiter = ImageRateLimiter(sleep=sleeper.sleep)

    async def operation() -> str:
        raise RateLimitError("429")

    with pytest.raises(RateLimitError):
        asyncio.run(limiter.run(operation))
    assert sleeper.delays == [2.0, 5.0, 10.0, 20.0]  # all four steps, then give up


def test_other_transient_bounded_by_max_retries() -> None:
    sleeper = _Sleeper()
    limiter = ImageRateLimiter(max_retries=0, sleep=sleeper.sleep)

    async def operation() -> str:
        raise ProviderUnavailableError("503")

    with pytest.raises(ProviderUnavailableError):
        asyncio.run(limiter.run(operation))
    assert sleeper.delays == []  # max_retries=0 -> no retry


def test_max_one_concurrent_request() -> None:
    async def _no_sleep(_delay: float) -> None:
        return None

    limiter = ImageRateLimiter(sleep=_no_sleep)
    active = 0
    peak = 0

    async def operation() -> str:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)  # yield so overlap would be observable
        active -= 1
        return "ok"

    async def main() -> None:
        await asyncio.gather(*(limiter.run(operation) for _ in range(5)))

    asyncio.run(main())
    assert peak == 1  # the semaphore serialises image requests
