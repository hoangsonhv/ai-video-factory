"""Vendor-neutral request/response models for the speech provider layer."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class SpeechSynthesisRequest(BaseModel):
    """A single narration synthesis request, independent of any provider."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)
    voice: str = ""
    language: str = "vi"
    provider_options: Mapping[str, object] = Field(default_factory=dict)


class SpeechSynthesisResponse(BaseModel):
    """The result of synthesizing (and saving) one narration audio file."""

    model_config = ConfigDict(frozen=True)

    audio_path: Path
    provider: str
    voice: str
    duration_seconds: float = Field(ge=0.0)
    sample_rate: int = Field(gt=0)
    metadata: Mapping[str, object] = Field(default_factory=dict)


@dataclass(frozen=True)
class SynthesizedAudio:
    """Provider-agnostic audio result returned by a low-level TTS client."""

    data: bytes
    sample_rate: int
    duration_seconds: float
