"""Tests for the provider factory (config-driven selection)."""

from __future__ import annotations

import pytest

from ai_video_factory.errors import ConfigurationError
from ai_video_factory.infrastructure.config.settings import Settings
from ai_video_factory.infrastructure.providers.factory.provider_factory import ProviderFactory
from ai_video_factory.infrastructure.providers.gemini.provider import GeminiProvider


def test_creates_gemini_by_default() -> None:
    settings = Settings(_env_file=None)
    provider = ProviderFactory.create(settings)
    assert isinstance(provider, GeminiProvider)


def test_unknown_provider_raises_configuration_error() -> None:
    settings = Settings(_env_file=None, provider={"provider": "does-not-exist"})
    with pytest.raises(ConfigurationError):
        ProviderFactory.create(settings)


def test_supported_providers_lists_gemini() -> None:
    assert "gemini" in ProviderFactory.supported_providers()


def test_map_status_to_error_classifies_codes() -> None:
    from ai_video_factory.infrastructure.providers.base.errors import (
        AuthenticationError,
        InvalidResponseError,
        ProviderUnavailableError,
        RateLimitError,
    )
    from ai_video_factory.infrastructure.providers.gemini.client import map_status_to_error

    assert isinstance(map_status_to_error(401, "x"), AuthenticationError)
    assert isinstance(map_status_to_error(429, "x"), RateLimitError)
    assert isinstance(map_status_to_error(503, "x"), ProviderUnavailableError)
    assert isinstance(map_status_to_error(418, "x"), InvalidResponseError)
