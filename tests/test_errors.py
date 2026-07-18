"""Tests for the application exception hierarchy (docs/ai-tool.md §7)."""

from __future__ import annotations

import pytest

from ai_video_factory.errors import (
    AppError,
    ApplicationError,
    ConfigurationError,
    DomainError,
    InfrastructureError,
    MediaError,
    PersistenceError,
    ProviderError,
)


@pytest.mark.parametrize(
    "error_type",
    [
        DomainError,
        ApplicationError,
        InfrastructureError,
        ProviderError,
        PersistenceError,
        MediaError,
        ConfigurationError,
    ],
)
def test_every_error_descends_from_app_error(error_type: type[AppError]) -> None:
    assert issubclass(error_type, AppError)


@pytest.mark.parametrize("error_type", [ProviderError, PersistenceError, MediaError])
def test_infrastructure_errors_share_base(error_type: type[InfrastructureError]) -> None:
    assert issubclass(error_type, InfrastructureError)


def test_app_error_carries_message_and_context() -> None:
    error = AppError("boom", context={"stage": "IMAGE"})
    assert error.message == "boom"
    assert error.context == {"stage": "IMAGE"}
    assert str(error) == "boom"


def test_provider_error_retryable_flag() -> None:
    assert ProviderError("rate limited", retryable=True).retryable is True
    assert ProviderError("bad request").retryable is False
