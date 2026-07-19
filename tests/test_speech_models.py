"""Tests for the speech request/response models."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_video_factory.infrastructure.providers.speech.base.models import (
    SpeechSynthesisRequest,
    SpeechSynthesisResponse,
    SynthesizedAudio,
)


def test_request_defaults() -> None:
    request = SpeechSynthesisRequest(text="Xin chào")
    assert request.language == "vi"
    assert request.voice == ""
    assert dict(request.provider_options) == {}


def test_request_requires_non_empty_text() -> None:
    with pytest.raises(ValidationError):
        SpeechSynthesisRequest(text="")


def test_response_fields() -> None:
    response = SpeechSynthesisResponse(
        audio_path=Path("output/audio/narration.mp3"),
        provider="gemini_tts",
        voice="Kore",
        duration_seconds=12.5,
        sample_rate=24000,
    )
    assert response.audio_path.name == "narration.mp3"
    assert response.sample_rate == 24000


def test_response_rejects_non_positive_sample_rate() -> None:
    with pytest.raises(ValidationError):
        SpeechSynthesisResponse(
            audio_path=Path("a.mp3"),
            provider="p",
            voice="v",
            duration_seconds=1.0,
            sample_rate=0,
        )


def test_synthesized_audio_is_a_frozen_dataclass() -> None:
    audio = SynthesizedAudio(data=b"pcm", sample_rate=24000, duration_seconds=1.0)
    assert audio.data == b"pcm"
