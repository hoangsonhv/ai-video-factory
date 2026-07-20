"""Exponential-backoff retry policy for provider calls.

Retries only transient failures — rate limit (429), provider unavailable
(500/502/503/504) and timeout (including connection and read timeouts) — with
exponential backoff. Terminal errors (authentication, invalid response) are
never retried.

Optional **jitter** spreads retries out so many concurrent callers hitting the
same outage do not all wake at the same instant and re-stampede the provider.
It is opt-in (``jitter=0.0``) so existing callers keep their exact timing.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from ai_video_factory.infrastructure.providers.base.errors import (
    AIProviderError,
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
)

_T = TypeVar("_T")

RETRYABLE_ERRORS: tuple[type[AIProviderError], ...] = (
    RateLimitError,
    ProviderUnavailableError,
    TimeoutError,
)

RetryHook = Callable[[int, float, AIProviderError], None]
"""Called before each sleep with ``(attempt, delay, error)`` — for logs/counts."""


class RetryPolicy:
    """Retry an async operation on transient provider errors."""

    def __init__(
        self,
        *,
        max_retries: int,
        base_delay: float = 0.5,
        max_delay: float = 8.0,
        jitter: float = 0.0,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        on_retry: RetryHook | None = None,
        rng: Callable[[float, float], float] | None = None,
    ) -> None:
        self._max_retries = max(max_retries, 0)
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._jitter = max(jitter, 0.0)
        self._sleep = sleep if sleep is not None else asyncio.sleep
        self._on_retry = on_retry
        self._rng = rng if rng is not None else random.uniform

    def _delay_for(self, attempt: int, exc: AIProviderError) -> float:
        """Back-off before the next attempt, honouring a server hint if given."""
        # Honour the server's back-off hint (e.g. a 429 ``retryDelay``) when
        # present, so we do not hammer the API; otherwise fall back to
        # exponential backoff. Both are capped by ``max_delay``.
        retry_after = getattr(exc, "retry_after", None)
        if isinstance(retry_after, int | float):
            delay = min(self._max_delay, float(retry_after))
        else:
            delay = min(self._max_delay, self._base_delay * (2**attempt))
        if self._jitter:
            delay *= 1.0 + self._rng(-self._jitter, self._jitter)
        return max(delay, 0.0)

    async def run(self, operation: Callable[[], Awaitable[_T]]) -> _T:
        """Run ``operation``, retrying transient failures with backoff.

        Re-raises the last error once retries are exhausted.
        """
        attempt = 0
        while True:
            try:
                return await operation()
            except RETRYABLE_ERRORS as exc:
                if attempt >= self._max_retries:
                    raise
                delay = self._delay_for(attempt, exc)
                if self._on_retry is not None:
                    self._on_retry(attempt + 1, delay, exc)
                await self._sleep(delay)
                attempt += 1
