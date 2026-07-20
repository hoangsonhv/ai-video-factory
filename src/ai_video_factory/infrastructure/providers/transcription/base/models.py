"""Vendor-neutral request/response models for the transcription provider layer."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TranscriptionRequest(BaseModel):
    """A request to transcribe one narration audio file into timed segments."""

    model_config = ConfigDict(frozen=True)

    audio_path: Path
    language: str = "vi"
    reference_text: str = ""
    provider_options: Mapping[str, object] = Field(default_factory=dict)


class TranscriptionSegment(BaseModel):
    """One timed subtitle segment (start/end in seconds, aligned to the audio)."""

    model_config = ConfigDict(frozen=True)

    start: float = Field(ge=0.0)
    end: float = Field(ge=0.0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def _end_after_start(self) -> TranscriptionSegment:
        if self.end < self.start:
            raise ValueError("segment end must be >= start")
        return self


class TranscriptionResult(BaseModel):
    """The result of transcribing one audio file into ordered timed segments."""

    model_config = ConfigDict(frozen=True)

    segments: tuple[TranscriptionSegment, ...]
    provider: str
    language: str
    metadata: Mapping[str, object] = Field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        """End time of the last segment (0.0 when there are no segments)."""
        return self.segments[-1].end if self.segments else 0.0
