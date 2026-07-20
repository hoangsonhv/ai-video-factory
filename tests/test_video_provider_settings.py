"""Tests for the video-provider configuration section (VIDEO_PROVIDER family)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_video_factory.infrastructure.config.settings import (
    VideoProviderSettings,
    load_settings,
)


def test_defaults_select_the_development_mock_provider() -> None:
    settings = VideoProviderSettings()

    assert settings.provider == "mock"
    assert settings.model == "mock-slideshow"
    assert settings.timeout == 300.0
    assert settings.retry_count == 1
    assert settings.api_key is None


def test_environment_overrides_every_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__PROVIDER", "mock")
    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__MODEL", "custom-model")
    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__TIMEOUT", "45")
    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__RETRY_COUNT", "4")

    video_provider = load_settings().video_provider

    assert video_provider.provider == "mock"
    assert video_provider.model == "custom-model"
    assert video_provider.timeout == 45.0
    assert video_provider.retry_count == 4


def test_a_blank_api_key_reads_as_unset() -> None:
    assert VideoProviderSettings.model_validate({"api_key": "   "}).api_key is None


def test_the_api_key_is_never_serialized() -> None:
    settings = VideoProviderSettings.model_validate({"api_key": "secret-value"})

    assert "secret-value" not in str(settings.model_dump())


def test_a_non_positive_timeout_is_rejected() -> None:
    with pytest.raises(ValidationError):
        VideoProviderSettings(timeout=0)


def test_a_negative_retry_count_is_rejected() -> None:
    with pytest.raises(ValidationError):
        VideoProviderSettings(retry_count=-1)


def test_the_video_composition_section_is_unaffected() -> None:
    """The Sprint 017 compose settings must keep their own namespace."""
    settings = load_settings()

    assert settings.video.ffmpeg_path == "ffmpeg"
    assert settings.video.width == 1080
    assert settings.video.retry_count == 1
    assert settings.video_provider.provider == "mock"
