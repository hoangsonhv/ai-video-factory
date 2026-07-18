"""Error hierarchy for the AI provider layer.

These descend from the application's infrastructure ``ProviderError`` so the
whole system keeps a single ``AppError`` root (docs/ai-tool.md §7). Concrete
providers translate their SDK exceptions into these types at the boundary;
raw vendor exceptions never propagate outward.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ai_video_factory.errors import ProviderError


class AIProviderError(ProviderError):
    """Base class for any AI/LLM provider failure."""


class AuthenticationError(AIProviderError):
    """The provider rejected the credentials (missing or invalid API key)."""


class RateLimitError(AIProviderError):
    """The provider returned a rate-limit response (HTTP 429). Retryable."""

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, retryable=True, context=context)
        self.retry_after = retry_after


class TimeoutError(AIProviderError):
    """The provider did not respond within the configured timeout. Retryable."""

    def __init__(self, message: str, *, context: Mapping[str, Any] | None = None) -> None:
        super().__init__(message, retryable=True, context=context)


class ProviderUnavailableError(AIProviderError):
    """The provider is temporarily unavailable (HTTP 503). Retryable."""

    def __init__(self, message: str, *, context: Mapping[str, Any] | None = None) -> None:
        super().__init__(message, retryable=True, context=context)


class InvalidResponseError(AIProviderError):
    """The provider returned a malformed or unusable response. Terminal."""
