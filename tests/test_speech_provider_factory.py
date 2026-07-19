"""Tests for the speech provider factory (config-driven selection)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_video_factory.errors import ConfigurationError
from ai_video_factory.infrastructure.config.settings import Settings
from ai_video_factory.infrastructure.media.audio_storage import AudioStorage
from ai_video_factory.infrastructure.providers.speech.factory.speech_provider_factory import (
    SpeechProviderFactory,
)
from ai_video_factory.infrastructure.providers.speech.gemini.provider import GeminiSpeechProvider


def test_creates_gemini_tts_by_default(tmp_path: Path) -> None:
    provider = SpeechProviderFactory.create(Settings(_env_file=None), AudioStorage(tmp_path))
    assert isinstance(provider, GeminiSpeechProvider)


def test_unknown_provider_raises(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, speech_provider={"provider": "does-not-exist"})
    with pytest.raises(ConfigurationError):
        SpeechProviderFactory.create(settings, AudioStorage(tmp_path))


def test_api_key_falls_back_to_llm_provider_key(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, provider={"api_key": "llm-key"})
    provider = SpeechProviderFactory.create(settings, AudioStorage(tmp_path))
    assert isinstance(provider, GeminiSpeechProvider)


def test_supported_providers(tmp_path: Path) -> None:
    assert "gemini_tts" in SpeechProviderFactory.supported_providers()
