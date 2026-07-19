"""Persist speech-synthesis metadata to a JSON file."""

from __future__ import annotations

import json
from pathlib import Path

from ai_video_factory.infrastructure.providers.speech.base.models import SpeechSynthesisResponse


def write_audio_metadata(path: Path, response: SpeechSynthesisResponse) -> None:
    """Write the audio metadata (duration/voice/provider/sample_rate) as UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "duration": response.duration_seconds,
        "voice": response.voice,
        "provider": response.provider,
        "sample_rate": response.sample_rate,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
