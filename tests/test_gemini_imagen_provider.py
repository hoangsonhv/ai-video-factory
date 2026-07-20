"""Tests for GeminiImagenProvider (fake client + real temp storage, no API)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ai_video_factory.infrastructure.config.settings import ImageProviderSettings
from ai_video_factory.infrastructure.media.image_storage import ImageStorage
from ai_video_factory.infrastructure.providers.base.errors import (
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
)
from ai_video_factory.infrastructure.providers.image.base.models import ImageGenerationRequest
from ai_video_factory.infrastructure.providers.image.gemini.provider import GeminiImagenProvider
from ai_video_factory.shared.health import HealthStatus


class FakeImagenClient:
    def __init__(
        self,
        *,
        data: bytes = b"PNG",
        error: Exception | None = None,
        fail_times: int = 0,
        delay: float = 0.0,
    ) -> None:
        self._data = data
        self._error = error
        self._fail_times = fail_times
        self._delay = delay
        self.calls = 0

    async def generate(self, request: ImageGenerationRequest, *, model: str) -> bytes:
        self.calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._fail_times > 0:
            self._fail_times -= 1
            raise RateLimitError("429")
        if self._error is not None:
            raise self._error
        return self._data

    async def list_models(self) -> list[str]:
        if self._error is not None:
            raise self._error
        return ["gemini-2.5-flash-image"]


def _settings(**overrides: object) -> ImageProviderSettings:
    base: dict[str, object] = {"retry_count": 0, "timeout": 5.0}
    base.update(overrides)
    return ImageProviderSettings(**base)


def _request() -> ImageGenerationRequest:
    return ImageGenerationRequest(prompt="a lone cultivator", aspect_ratio="9:16")


def test_generate_saves_image_and_returns_response(tmp_path: Path) -> None:
    storage = ImageStorage(tmp_path / "images")
    client = FakeImagenClient(data=b"IMAGEBYTES")
    provider = GeminiImagenProvider(_settings(), storage, client=client)

    response = asyncio.run(provider.generate(_request()))

    assert response.image_path.exists()
    assert response.image_path.read_bytes() == b"IMAGEBYTES"
    assert response.provider == "gemini_imagen"
    assert response.image_path.name == "image_001.png"


def test_generate_without_api_key_raises(tmp_path: Path) -> None:
    provider = GeminiImagenProvider(_settings(), ImageStorage(tmp_path))
    with pytest.raises(AuthenticationError):
        asyncio.run(provider.generate(_request()))


def test_generate_times_out(tmp_path: Path) -> None:
    client = FakeImagenClient(delay=1.0)
    provider = GeminiImagenProvider(
        _settings(retry_count=0, timeout=0.01), ImageStorage(tmp_path), client=client
    )
    with pytest.raises(TimeoutError):
        asyncio.run(provider.generate(_request()))


def test_generate_retries_transient_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    client = FakeImagenClient(fail_times=1)
    provider = GeminiImagenProvider(_settings(retry_count=1), ImageStorage(tmp_path), client=client)

    response = asyncio.run(provider.generate(_request()))
    assert response.image_path.exists()
    assert client.calls == 2


def test_probe_generation_single_call_and_does_not_save(tmp_path: Path) -> None:
    storage = ImageStorage(tmp_path / "images")
    client = FakeImagenClient(data=b"X")
    provider = GeminiImagenProvider(_settings(), storage, client=client)

    asyncio.run(provider.probe_generation(_request()))

    assert client.calls == 1  # one shot, no retry
    assert not (tmp_path / "images").exists()  # nothing written to disk


def test_probe_generation_raises_without_key(tmp_path: Path) -> None:
    provider = GeminiImagenProvider(_settings(), ImageStorage(tmp_path))
    with pytest.raises(AuthenticationError):
        asyncio.run(provider.probe_generation(_request()))


def test_probe_generation_propagates_rate_limit(tmp_path: Path) -> None:
    client = FakeImagenClient(error=RateLimitError("429"))
    provider = GeminiImagenProvider(_settings(), ImageStorage(tmp_path), client=client)
    with pytest.raises(RateLimitError):
        asyncio.run(provider.probe_generation(_request()))


def test_health_check_warn_without_key(tmp_path: Path) -> None:
    provider = GeminiImagenProvider(_settings(), ImageStorage(tmp_path))
    assert asyncio.run(provider.health_check()).status is HealthStatus.WARN


def test_health_check_ok(tmp_path: Path) -> None:
    provider = GeminiImagenProvider(_settings(), ImageStorage(tmp_path), client=FakeImagenClient())
    assert asyncio.run(provider.health_check()).status is HealthStatus.OK


def test_health_check_fail(tmp_path: Path) -> None:
    client = FakeImagenClient(error=ProviderUnavailableError("503"))
    provider = GeminiImagenProvider(_settings(), ImageStorage(tmp_path), client=client)
    assert asyncio.run(provider.health_check()).status is HealthStatus.FAIL
