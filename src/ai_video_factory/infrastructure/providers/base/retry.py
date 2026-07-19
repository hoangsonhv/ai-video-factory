"""Exponential-backoff retry policy for provider calls.

Retries only transient failures — rate limit (429), provider unavailable
(503) and timeout — with exponential backoff. Terminal errors (authentication,
invalid response) are never retried.
"""

from __future__ import annotations

import asyncio
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


class RetryPolicy:
    """Retry an async operation on transient provider errors."""

    def __init__(
        self,
        *,
        max_retries: int,
        base_delay: float = 0.5,
        max_delay: float = 8.0,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._max_retries = max(max_retries, 0)
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._sleep = sleep if sleep is not None else asyncio.sleep

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
                # Honour the server's back-off hint (e.g. a 429 ``retryDelay``)
                # when present, so we do not hammer the API; otherwise fall back
                # to exponential backoff. Both are capped by ``max_delay``.
                retry_after = getattr(exc, "retry_after", None)
                if isinstance(retry_after, int | float):
                    delay = min(self._max_delay, float(retry_after))
                else:
                    delay = min(self._max_delay, self._base_delay * (2**attempt))
                await self._sleep(delay)
                attempt += 1
