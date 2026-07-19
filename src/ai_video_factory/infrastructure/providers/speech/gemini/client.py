"""Low-level Gemini TTS client wrapping the official ``google-genai`` SDK.

The only speech module that touches the vendor SDK. Gemini TTS returns raw PCM
(16-bit mono, 24 kHz); since transcoding to MP3 needs ffmpeg (out of scope),
the PCM is wrapped into a WAV container with the pure-Python ``wave`` module.
Translates SDK errors into the shared provider error hierarchy; SDK imported
lazily.
"""

from __future__ import annotations

import io
import wave
from typing import Protocol

from ai_video_factory.infrastructure.providers.base.errors import InvalidResponseError
from ai_video_factory.infrastructure.providers.gemini.client import map_status_to_error
from ai_video_factory.infrastructure.providers.speech.base.models import (
    SpeechSynthesisRequest,
    SynthesizedAudio,
)

_SAMPLE_RATE = 24000
_SAMPLE_WIDTH = 2  # 16-bit PCM
_GEMINI_TTS_VOICES: tuple[str, ...] = (
    "Kore",
    "Puck",
    "Charon",
    "Aoede",
    "Fenrir",
    "Leda",
    "Orus",
    "Zephyr",
)


def pcm_to_wav(pcm: bytes, *, sample_rate: int = _SAMPLE_RATE) -> bytes:
    """Wrap raw 16-bit mono PCM into a WAV container (no external tools)."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(_SAMPLE_WIDTH)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buffer.getvalue()


class GeminiTtsClient(Protocol):
    """The subset of Gemini TTS operations the provider needs."""

    async def synthesize(
        self, request: SpeechSynthesisRequest, *, model: str, voice: str
    ) -> SynthesizedAudio: ...

    async def list_voices(self) -> list[str]: ...


class RealGeminiTtsClient:
    """Concrete :class:`GeminiTtsClient` backed by ``google-genai`` (Gemini TTS)."""

    def __init__(self, api_key: str) -> None:
        from google import genai  # lazy: only needed when a live client is built
        from google.genai import errors as genai_errors
        from google.genai import types as genai_types

        self._client = genai.Client(api_key=api_key)
        self._types = genai_types
        self._api_error: type[Exception] = genai_errors.APIError

    async def synthesize(
        self, request: SpeechSynthesisRequest, *, model: str, voice: str
    ) -> SynthesizedAudio:
        config = self._types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=self._types.SpeechConfig(
                voice_config=self._types.VoiceConfig(
                    prebuilt_voice_config=self._types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        )
        try:
            response = await self._client.aio.models.generate_content(
                model=model, contents=request.text, config=config
            )
        except self._api_error as exc:
            raise map_status_to_error(int(getattr(exc, "code", 0) or 0), str(exc)) from exc

        pcm = self._extract_pcm(response)
        duration = (len(pcm) / _SAMPLE_WIDTH) / _SAMPLE_RATE
        return SynthesizedAudio(
            data=pcm_to_wav(pcm), sample_rate=_SAMPLE_RATE, duration_seconds=duration
        )

    async def list_voices(self) -> list[str]:
        return list(_GEMINI_TTS_VOICES)

    @staticmethod
    def _extract_pcm(response: object) -> bytes:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            raise InvalidResponseError("speech provider returned no audio")
        parts = getattr(getattr(candidates[0], "content", None), "parts", None) or []
        for part in parts:
            data = getattr(getattr(part, "inline_data", None), "data", None)
            if isinstance(data, bytes) and data:
                return data
        raise InvalidResponseError("speech provider returned empty audio data")
