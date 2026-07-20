"""Tests for the transcription provider factory (config-driven selection)."""

from __future__ import annotations

import pytest

from ai_video_factory.errors import ConfigurationError
from ai_video_factory.infrastructure.config.settings import Settings
from ai_video_factory.infrastructure.providers.transcription.factory.transcription_provider_factory import (  # noqa: E501
    TranscriptionProviderFactory,
)
from ai_video_factory.infrastructure.providers.transcription.gemini.provider import (
    GeminiTranscriptionProvider,
)


def test_creates_gemini_transcription_by_default() -> None:
    provider = TranscriptionProviderFactory.create(Settings(_env_file=None))
    assert isinstance(provider, GeminiTranscriptionProvider)


def test_unknown_provider_raises() -> None:
    settings = Settings(_env_file=None, transcription_provider={"provider": "does-not-exist"})
    with pytest.raises(ConfigurationError):
        TranscriptionProviderFactory.create(settings)


def test_api_key_falls_back_to_llm_provider_key() -> None:
    settings = Settings(_env_file=None, provider={"api_key": "llm-key"})
    provider = TranscriptionProviderFactory.create(settings)
    # With the reused key the provider has a live client (health is OK, not WARN).
    import asyncio

    from ai_video_factory.shared.health import HealthStatus

    assert asyncio.run(provider.health_check()).status is HealthStatus.OK


def test_supported_providers() -> None:
    assert "gemini_transcription" in TranscriptionProviderFactory.supported_providers()
