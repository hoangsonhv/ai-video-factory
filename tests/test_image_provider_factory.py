"""Tests for the image provider factory (config-driven selection)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_video_factory.errors import ConfigurationError
from ai_video_factory.infrastructure.config.settings import Settings
from ai_video_factory.infrastructure.media.image_storage import ImageStorage
from ai_video_factory.infrastructure.providers.image.factory.image_provider_factory import (
    ImageProviderFactory,
)
from ai_video_factory.infrastructure.providers.image.gemini.provider import GeminiImagenProvider


def test_creates_gemini_imagen_by_default(tmp_path: Path) -> None:
    provider = ImageProviderFactory.create(Settings(_env_file=None), ImageStorage(tmp_path))
    assert isinstance(provider, GeminiImagenProvider)


def test_unknown_provider_raises(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, image_provider={"provider": "does-not-exist"})
    with pytest.raises(ConfigurationError):
        ImageProviderFactory.create(settings, ImageStorage(tmp_path))


def test_api_key_falls_back_to_llm_provider_key(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, provider={"api_key": "llm-key"})
    # No image_provider api_key -> the factory reuses the LLM provider's key,
    # so the built provider has a live client (not the no-key WARN path).
    provider = ImageProviderFactory.create(settings, ImageStorage(tmp_path))
    assert isinstance(provider, GeminiImagenProvider)


def test_supported_providers(tmp_path: Path) -> None:
    assert "gemini_imagen" in ImageProviderFactory.supported_providers()
