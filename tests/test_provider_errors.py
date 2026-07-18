"""Tests for the AI provider error hierarchy."""

from __future__ import annotations

import pytest

from ai_video_factory.errors import AppError, InfrastructureError, ProviderError
from ai_video_factory.infrastructure.providers.base.errors import (
    AIProviderError,
    AuthenticationError,
    InvalidResponseError,
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
)


@pytest.mark.parametrize(
    "error_type",
    [
        AuthenticationError,
        RateLimitError,
        TimeoutError,
        ProviderUnavailableError,
        InvalidResponseError,
    ],
)
def test_all_provider_errors_are_ai_provider_errors(
    error_type: type[AIProviderError],
) -> None:
    assert issubclass(error_type, AIProviderError)


def test_ai_provider_error_integrates_with_app_hierarchy() -> None:
    assert issubclass(AIProviderError, ProviderError)
    assert issubclass(AIProviderError, InfrastructureError)
    assert issubclass(AIProviderError, AppError)


def test_retryable_flags() -> None:
    assert RateLimitError("429").retryable is True
    assert TimeoutError("slow").retryable is True
    assert ProviderUnavailableError("503").retryable is True
    assert AuthenticationError("401").retryable is False
    assert InvalidResponseError("bad").retryable is False


def test_rate_limit_carries_retry_after() -> None:
    error = RateLimitError("429", retry_after=2.5)
    assert error.retry_after == 2.5
