"""Request/result models for the story pipeline (infrastructure)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ai_video_factory.domain.value_objects.chapter import StoryChapter
from ai_video_factory.domain.value_objects.idea import StoryIdea
from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.domain.value_objects.outline import StoryOutline


class PipelineRequest(BaseModel):
    """The inputs that drive a full idea → image-prompts pipeline run."""

    model_config = ConfigDict(frozen=True)

    topic: str = Field(min_length=1)
    style: str = Field(min_length=1)
    target_platform: str = Field(min_length=1)
    chapter_count: int = Field(default=10, ge=1)
    target_duration: str = "60s"
    language: str = "vi"
    image_count: int = Field(default=6, ge=1)


class PipelineResult(BaseModel):
    """The typed outputs of a completed pipeline run and the files written."""

    model_config = ConfigDict(frozen=True)

    ideas: list[StoryIdea]
    outline: StoryOutline
    chapter: StoryChapter
    image_prompts: list[ImagePrompt]
    outputs: list[Path]
