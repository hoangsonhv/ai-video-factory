"""Storyboard value objects (domain layer).

A storyboard is the movie flattened onto a **timeline**: every shot of every
scene in order, each with its absolute position, the narration that plays over
it, and the prompts needed to render it. Pure and immutable
(docs/ai-tool.md §2.1) — no I/O, no vendor SDKs. This is the schema of
``output/storyboard.json``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AudioSegment(BaseModel):
    """The slice of the narration track that plays over one shot."""

    model_config = ConfigDict(frozen=True)

    source: str = ""
    start: float = Field(default=0.0, ge=0.0)
    end: float = Field(default=0.0, ge=0.0)

    @property
    def duration(self) -> float:
        """Length of the slice in seconds."""
        return max(0.0, self.end - self.start)


class StoryboardShot(BaseModel):
    """One shot placed on the timeline, ready to render.

    ``speech_start``/``speech_end`` are absolute seconds from the start of the
    movie, so a shot's position never depends on reading the ones before it.
    """

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=1)
    scene_id: int = Field(ge=1)
    order: int = Field(ge=1)
    duration: int = Field(gt=0)
    camera: str = ""
    camera_motion: str = ""
    lens: str = ""
    framing: str = ""
    transition: str = ""
    character: str = ""
    action: str = ""
    expression: str = ""
    environment: str = ""
    lighting: str = ""
    speech_start: float = Field(default=0.0, ge=0.0)
    speech_end: float = Field(default=0.0, ge=0.0)
    subtitle: str = ""
    image_prompt: str = ""
    video_prompt: str = ""
    audio_segment: AudioSegment = Field(default_factory=AudioSegment)


class Storyboard(BaseModel):
    """Every shot of a movie, in order, on one timeline."""

    model_config = ConfigDict(frozen=True)

    title: str = ""
    style: str = ""
    total_duration: float = Field(default=0.0, ge=0.0)
    narration_duration: float = Field(default=0.0, ge=0.0)
    shots: tuple[StoryboardShot, ...] = ()

    @property
    def shot_count(self) -> int:
        """How many shots the storyboard holds."""
        return len(self.shots)

    @property
    def scene_count(self) -> int:
        """How many distinct scenes contributed shots."""
        return len({shot.scene_id for shot in self.shots})

    @property
    def drift(self) -> float:
        """Signed gap between the shot timeline and the narration.

        Positive means the shots run longer than the narration; negative means
        the narration outlasts the shots. ``0.0`` when no narration is known.
        """
        if not self.narration_duration:
            return 0.0
        return round(self.total_duration - self.narration_duration, 3)
