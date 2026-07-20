"""Tests for PollinationsImageProvider (fake client + temp storage, no network)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ai_video_factory.infrastructure.config.settings import ImageProviderSettings
from ai_video_factory.infrastructure.media.image_storage import ImageStorage
from ai_video_factory.infrastructure.providers.base.errors import (
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
)
from ai_video_factory.infrastructure.providers.image.base.models import ImageGenerationRequest
from ai_video_factory.infrastructure.providers.image.pollinations.provider import (
    PollinationsImageProvider,
)
from ai_video_factory.shared.health import HealthStatus


class FakePollinationsClient:
    def __init__(
        self,
        *,
        data: bytes = b"PNG",
        error: Exception | None = None,
        fail_times: int = 0,
        delay: float = 0.0,
        models: list[str] | None = None,
    ) -> None:
        self._data = data
        self._error = error
        self._fail_times = fail_times
        self._delay = delay
        self._models = models if models is not None else ["flux", "turbo"]
        self.calls = 0

    async def generate(self, request: ImageGenerationRequest, *, model: str) -> bytes:
        self.calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._fail_times > 0:
            self._fail_times -= 1
            raise ProviderUnavailableError("503")
        if self._error is not None:
            raise self._error
        return self._data

    async def list_models(self) -> list[str]:
        if self._error is not None:
            raise self._error
        return self._models


def _settings(**overrides: object) -> ImageProviderSettings:
    base: dict[str, object] = {"provider": "pollinations", "retry_count": 0, "timeout": 5.0}
    base.update(overrides)
    return ImageProviderSettings(**base)


def _request() -> ImageGenerationRequest:
    return ImageGenerationRequest(prompt="a lone cultivator", aspect_ratio="9:16")


def test_generate_saves_image_and_returns_response(tmp_path: Path) -> None:
    storage = ImageStorage(tmp_path / "images")
    client = FakePollinationsClient(data=b"IMAGEBYTES")
    provider = PollinationsImageProvider(_settings(), storage, client=client)

    response = asyncio.run(provider.generate(_request()))

    assert response.image_path.exists()
    assert response.image_path.read_bytes() == b"IMAGEBYTES"
    assert response.provider == "pollinations"
    assert response.model == "flux"
    assert response.image_path.name == "image_001.png"


def test_generate_needs_no_api_key(tmp_path: Path) -> None:
    # Unlike Gemini, Pollinations builds a live client without any key.
    provider = PollinationsImageProvider(_settings(), ImageStorage(tmp_path))
    assert provider._client is not None  # asserting a live client exists without any key


def test_generate_retries_transient_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    client = FakePollinationsClient(fail_times=2)
    provider = PollinationsImageProvider(
        _settings(retry_count=3), ImageStorage(tmp_path), client=client
    )

    response = asyncio.run(provider.generate(_request()))
    assert response.image_path.exists()
    assert client.calls == 3  # two failures + one success


def test_generate_exhausts_retries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    client = FakePollinationsClient(error=ProviderUnavailableError("503"))
    provider = PollinationsImageProvider(
        _settings(retry_count=3), ImageStorage(tmp_path), client=client
    )
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(provider.generate(_request()))


def test_generate_times_out(tmp_path: Path) -> None:
    client = FakePollinationsClient(delay=1.0)
    provider = PollinationsImageProvider(
        _settings(retry_count=0, timeout=0.01), ImageStorage(tmp_path), client=client
    )
    with pytest.raises(TimeoutError):
        asyncio.run(provider.generate(_request()))


def test_generate_propagates_rate_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A 429 is retried on the image rate-limiter's fixed backoff schedule and,
    # once exhausted, re-raised. Sleep is mocked so the schedule is instant.
    async def _no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    client = FakePollinationsClient(error=RateLimitError("429"))
    provider = PollinationsImageProvider(
        _settings(retry_count=0), ImageStorage(tmp_path), client=client
    )
    with pytest.raises(RateLimitError):
        asyncio.run(provider.generate(_request()))
    assert client.calls == 5  # initial + four backoff steps (2/5/10/20s)


def test_models_returns_list(tmp_path: Path) -> None:
    client = FakePollinationsClient(models=["flux", "turbo"])
    provider = PollinationsImageProvider(_settings(), ImageStorage(tmp_path), client=client)
    assert asyncio.run(provider.models()) == ["flux", "turbo"]


def test_health_check_ok(tmp_path: Path) -> None:
    provider = PollinationsImageProvider(
        _settings(), ImageStorage(tmp_path), client=FakePollinationsClient()
    )
    assert asyncio.run(provider.health_check()).status is HealthStatus.OK


def test_health_check_fail(tmp_path: Path) -> None:
    client = FakePollinationsClient(error=ProviderUnavailableError("503"))
    provider = PollinationsImageProvider(_settings(), ImageStorage(tmp_path), client=client)
    assert asyncio.run(provider.health_check()).status is HealthStatus.FAIL


def test_probe_generation_single_call_and_does_not_save(tmp_path: Path) -> None:
    storage = ImageStorage(tmp_path / "images")
    client = FakePollinationsClient(data=b"X")
    provider = PollinationsImageProvider(_settings(), storage, client=client)

    asyncio.run(provider.probe_generation(_request()))

    assert client.calls == 1
    assert not (tmp_path / "images").exists()  # nothing written to disk
