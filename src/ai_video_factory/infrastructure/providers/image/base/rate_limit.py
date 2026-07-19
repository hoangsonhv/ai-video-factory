"""Rate-limit-aware retry for image generation.

Serialises image requests so at most one is in flight, detects HTTP 429 rate
limits separately from other transient failures, and backs off on a fixed
schedule — honouring a server ``Retry-After`` when present — before continuing.
It never retries immediately (the minimum wait is the first schedule step).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from ai_video_factory.infrastructure.providers.base.errors import (
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
)

_T = TypeVar("_T")

# Back-off (seconds) applied on successive rate-limit (HTTP 429) retries.
BACKOFF_SCHEDULE: tuple[float, ...] = (2.0, 5.0, 10.0, 20.0)

# Other transient failures share the same schedule but are bounded by the
# configured retry count rather than the rate-limit schedule length.
_OTHER_TRANSIENT: tuple[type[Exception], ...] = (ProviderUnavailableError, TimeoutError)


class ImageRateLimiter:
    """Serialise image requests and retry rate-limited calls with backoff."""

    def __init__(
        self,
        *,
        max_retries: int = 0,
        backoff: tuple[float, ...] = BACKOFF_SCHEDULE,
        on_rate_limit: Callable[[str], None] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._max_retries = max(max_retries, 0)
        self._backoff = backoff
        self._on_rate_limit = on_rate_limit
        self._sleep = sleep if sleep is not None else asyncio.sleep
        self._gate = asyncio.Semaphore(1)  # at most one image request in flight

    async def run(self, operation: Callable[[], Awaitable[_T]]) -> _T:
        """Run ``operation`` serialised, retrying 429s and other transients.

        Re-raises the last error once the relevant retry budget is exhausted.
        """
        async with self._gate:
            rate_limit_attempt = 0
            other_attempt = 0
            while True:
                try:
                    return await operation()
                except RateLimitError as exc:
                    if rate_limit_attempt >= len(self._backoff):
                        raise
                    wait = self._wait_seconds(exc, rate_limit_attempt)
                    self._announce(wait)
                    await self._sleep(wait)
                    rate_limit_attempt += 1
                except _OTHER_TRANSIENT:
                    if other_attempt >= self._max_retries:
                        raise
                    index = min(other_attempt, len(self._backoff) - 1)
                    await self._sleep(self._backoff[index])
                    other_attempt += 1

    def _wait_seconds(self, exc: RateLimitError, attempt: int) -> float:
        """Return the wait before the next retry — never zero.

        A positive server ``Retry-After`` hint wins; otherwise the fixed
        exponential schedule for this attempt applies.
        """
        retry_after = exc.retry_after
        if retry_after is not None and retry_after > 0:
            return float(retry_after)
        return self._backoff[attempt]

    def _announce(self, wait: float) -> None:
        if self._on_rate_limit is not None:
            self._on_rate_limit(f"Rate limit reached, waiting {int(wait)} seconds...")
