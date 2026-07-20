"""Low-level Gemini transcription client wrapping ``google-genai``.

The only transcription module that touches the vendor SDK. It sends the
narration audio (inline) to a Gemini multimodal model and asks for a JSON list
of timed segments, then translates the reply and any SDK errors into the shared
provider types. The SDK is imported lazily.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from ai_video_factory.infrastructure.providers.base.errors import InvalidResponseError
from ai_video_factory.infrastructure.providers.gemini.client import map_status_to_error
from ai_video_factory.infrastructure.providers.transcription.base.models import (
    TranscriptionRequest,
    TranscriptionSegment,
)

_MIME_BY_SUFFIX: dict[str, str] = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
}


def _mime_type(path: Path) -> str:
    return _MIME_BY_SUFFIX.get(path.suffix.lower(), "audio/mpeg")


def _build_prompt(language: str, reference_text: str) -> str:
    prompt = (
        f"Transcribe this narration audio in {language}. Return ONLY a JSON array of "
        "segments, each an object with numeric 'start' and 'end' fields (seconds from "
        "the beginning of the audio) and a 'text' field. Split into short subtitle-sized "
        "lines and keep the timings aligned to when each line is spoken."
    )
    if reference_text.strip():
        prompt += (
            "\n\nUse this reference transcript for the exact wording (fix ASR errors to "
            f"match it):\n{reference_text.strip()}"
        )
    return prompt


def parse_segments(payload: str) -> list[TranscriptionSegment]:
    """Parse a Gemini JSON reply into validated :class:`TranscriptionSegment`s."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise InvalidResponseError(
            "transcription provider returned invalid JSON", context={"error": str(exc)}
        ) from exc
    raw = data.get("segments") if isinstance(data, dict) else data
    if not isinstance(raw, list) or not raw:
        raise InvalidResponseError("transcription provider returned no segments")
    segments: list[TranscriptionSegment] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        start = float(item.get("start", 0.0) or 0.0)
        end = float(item.get("end", start) or start)
        segments.append(TranscriptionSegment(start=start, end=max(end, start), text=text))
    if not segments:
        raise InvalidResponseError("transcription provider returned no usable segments")
    return segments


class GeminiTranscriptionClient(Protocol):
    """The subset of Gemini transcription operations the provider needs."""

    async def transcribe(
        self, request: TranscriptionRequest, *, model: str
    ) -> list[TranscriptionSegment]: ...


class RealGeminiTranscriptionClient:
    """Concrete client backed by ``google-genai`` (audio understanding)."""

    def __init__(self, api_key: str) -> None:
        from google import genai  # lazy: only needed when a live client is built
        from google.genai import errors as genai_errors
        from google.genai import types as genai_types

        self._client = genai.Client(api_key=api_key)
        self._types = genai_types
        self._api_error: type[Exception] = genai_errors.APIError

    async def transcribe(
        self, request: TranscriptionRequest, *, model: str
    ) -> list[TranscriptionSegment]:
        audio_part = self._types.Part.from_bytes(
            data=request.audio_path.read_bytes(), mime_type=_mime_type(request.audio_path)
        )
        config = self._types.GenerateContentConfig(response_mime_type="application/json")
        try:
            response = await self._client.aio.models.generate_content(
                model=model,
                contents=[_build_prompt(request.language, request.reference_text), audio_part],
                config=config,
            )
        except self._api_error as exc:
            raise map_status_to_error(int(getattr(exc, "code", 0) or 0), str(exc)) from exc
        return parse_segments(str(getattr(response, "text", "") or ""))
