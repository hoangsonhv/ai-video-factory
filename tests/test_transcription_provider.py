"""Tests for GeminiTranscriptionProvider (fake client, no real API)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ai_video_factory.infrastructure.config.settings import TranscriptionProviderSettings
from ai_video_factory.infrastructure.providers.base.errors import (
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
)
from ai_video_factory.infrastructure.providers.transcription.base.models import (
    TranscriptionRequest,
    TranscriptionSegment,
)
from ai_video_factory.infrastructure.providers.transcription.gemini.provider import (
    GeminiTranscriptionProvider,
)
from ai_video_factory.shared.health import HealthStatus


class FakeTranscriptionClient:
    def __init__(
        self,
        *,
        segments: list[TranscriptionSegment] | None = None,
        error: Exception | None = None,
        fail_times: int = 0,
        delay: float = 0.0,
    ) -> None:
        self._segments = segments or [TranscriptionSegment(start=0.0, end=1.0, text="Xin chào")]
        self._error = error
        self._fail_times = fail_times
        self._delay = delay
        self.calls = 0

    async def transcribe(
        self, request: TranscriptionRequest, *, model: str
    ) -> list[TranscriptionSegment]:
        self.calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._fail_times > 0:
            self._fail_times -= 1
            raise ProviderUnavailableError("503")
        if self._error is not None:
            raise self._error
        return self._segments


def _settings(**overrides: object) -> TranscriptionProviderSettings:
    base: dict[str, object] = {"retry_count": 0, "timeout": 5.0}
    base.update(overrides)
    return TranscriptionProviderSettings(**base)


def _request(tmp_path: Path) -> TranscriptionRequest:
    audio = tmp_path / "narration.mp3"
    audio.write_bytes(b"AUDIO")
    return TranscriptionRequest(audio_path=audio, language="vi", reference_text="Xin chào")


def test_transcribe_returns_result(tmp_path: Path) -> None:
    client = FakeTranscriptionClient(
        segments=[
            TranscriptionSegment(start=0.0, end=2.0, text="Một"),
            TranscriptionSegment(start=2.0, end=4.0, text="Hai"),
        ]
    )
    provider = GeminiTranscriptionProvider(_settings(), client=client)

    result = asyncio.run(provider.transcribe(_request(tmp_path)))

    assert result.provider == "gemini_transcription"
    assert result.language == "vi"
    assert len(result.segments) == 2
    assert result.duration_seconds == 4.0


def test_transcribe_without_api_key_raises(tmp_path: Path) -> None:
    provider = GeminiTranscriptionProvider(_settings())
    with pytest.raises(AuthenticationError):
        asyncio.run(provider.transcribe(_request(tmp_path)))


def test_transcribe_times_out(tmp_path: Path) -> None:
    client = FakeTranscriptionClient(delay=1.0)
    provider = GeminiTranscriptionProvider(_settings(retry_count=0, timeout=0.01), client=client)
    with pytest.raises(TimeoutError):
        asyncio.run(provider.transcribe(_request(tmp_path)))


def test_transcribe_retries_transient_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    client = FakeTranscriptionClient(fail_times=2)
    provider = GeminiTranscriptionProvider(_settings(retry_count=3), client=client)

    result = asyncio.run(provider.transcribe(_request(tmp_path)))
    assert len(result.segments) == 1
    assert client.calls == 3  # two failures + one success


def test_transcribe_exhausts_retries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    client = FakeTranscriptionClient(error=RateLimitError("429"))
    provider = GeminiTranscriptionProvider(_settings(retry_count=3), client=client)
    with pytest.raises(RateLimitError):
        asyncio.run(provider.transcribe(_request(tmp_path)))


def test_health_check_warn_without_key() -> None:
    provider = GeminiTranscriptionProvider(_settings())
    assert asyncio.run(provider.health_check()).status is HealthStatus.WARN


def test_health_check_ok_with_client() -> None:
    provider = GeminiTranscriptionProvider(_settings(), client=FakeTranscriptionClient())
    assert asyncio.run(provider.health_check()).status is HealthStatus.OK
