"""Tests for GeminiSpeechProvider (fake client + real temp storage, no API)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ai_video_factory.infrastructure.config.settings import SpeechProviderSettings
from ai_video_factory.infrastructure.media.audio_storage import AudioStorage
from ai_video_factory.infrastructure.providers.base.errors import (
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
)
from ai_video_factory.infrastructure.providers.speech.base.models import (
    SpeechSynthesisRequest,
    SynthesizedAudio,
)
from ai_video_factory.infrastructure.providers.speech.gemini.provider import GeminiSpeechProvider
from ai_video_factory.shared.health import HealthStatus


class FakeTtsClient:
    def __init__(
        self,
        *,
        error: Exception | None = None,
        fail_times: int = 0,
        delay: float = 0.0,
    ) -> None:
        self._error = error
        self._fail_times = fail_times
        self._delay = delay
        self.calls = 0

    async def synthesize(
        self, request: SpeechSynthesisRequest, *, model: str, voice: str
    ) -> SynthesizedAudio:
        self.calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._fail_times > 0:
            self._fail_times -= 1
            raise RateLimitError("429")
        if self._error is not None:
            raise self._error
        return SynthesizedAudio(data=b"WAVDATA", sample_rate=24000, duration_seconds=3.0)

    async def list_voices(self) -> list[str]:
        if self._error is not None:
            raise self._error
        return ["Kore", "Puck"]


def _settings(**overrides: object) -> SpeechProviderSettings:
    base: dict[str, object] = {"retry_count": 0, "timeout": 5.0}
    base.update(overrides)
    return SpeechProviderSettings(**base)


def _request() -> SpeechSynthesisRequest:
    return SpeechSynthesisRequest(text="Xin chào thế giới", language="vi")


def test_synthesize_saves_audio_and_returns_response(tmp_path: Path) -> None:
    storage = AudioStorage(tmp_path / "audio")
    provider = GeminiSpeechProvider(_settings(), storage, client=FakeTtsClient())

    response = asyncio.run(provider.synthesize(_request()))

    assert response.audio_path.exists()
    assert response.audio_path.read_bytes() == b"WAVDATA"
    assert response.audio_path.name == "narration.mp3"
    assert response.provider == "gemini_tts"
    assert response.voice == "Kore"
    assert response.sample_rate == 24000
    assert response.duration_seconds == 3.0


def test_request_voice_overrides_default(tmp_path: Path) -> None:
    provider = GeminiSpeechProvider(_settings(), AudioStorage(tmp_path), client=FakeTtsClient())
    request = SpeechSynthesisRequest(text="hi", voice="Puck")
    assert asyncio.run(provider.synthesize(request)).voice == "Puck"


def test_synthesize_without_api_key_raises(tmp_path: Path) -> None:
    provider = GeminiSpeechProvider(_settings(), AudioStorage(tmp_path))
    with pytest.raises(AuthenticationError):
        asyncio.run(provider.synthesize(_request()))


def test_synthesize_times_out(tmp_path: Path) -> None:
    client = FakeTtsClient(delay=1.0)
    provider = GeminiSpeechProvider(
        _settings(retry_count=0, timeout=0.01), AudioStorage(tmp_path), client=client
    )
    with pytest.raises(TimeoutError):
        asyncio.run(provider.synthesize(_request()))


def test_synthesize_retries_transient_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    client = FakeTtsClient(fail_times=1)
    provider = GeminiSpeechProvider(_settings(retry_count=1), AudioStorage(tmp_path), client=client)

    response = asyncio.run(provider.synthesize(_request()))
    assert response.audio_path.exists()
    assert client.calls == 2


def test_list_voices(tmp_path: Path) -> None:
    provider = GeminiSpeechProvider(_settings(), AudioStorage(tmp_path), client=FakeTtsClient())
    assert asyncio.run(provider.list_voices()) == ["Kore", "Puck"]


def test_health_check_warn_without_key(tmp_path: Path) -> None:
    provider = GeminiSpeechProvider(_settings(), AudioStorage(tmp_path))
    assert asyncio.run(provider.health_check()).status is HealthStatus.WARN


def test_health_check_ok(tmp_path: Path) -> None:
    provider = GeminiSpeechProvider(_settings(), AudioStorage(tmp_path), client=FakeTtsClient())
    assert asyncio.run(provider.health_check()).status is HealthStatus.OK


def test_health_check_fail(tmp_path: Path) -> None:
    client = FakeTtsClient(error=ProviderUnavailableError("503"))
    provider = GeminiSpeechProvider(_settings(), AudioStorage(tmp_path), client=client)
    assert asyncio.run(provider.health_check()).status is HealthStatus.FAIL
