"""Story-outline value objects (domain layer).

Pure, immutable models describing a full story outline expanded from a single
story idea. No I/O or framework coupling (docs/ai-tool.md §2.1).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ChapterOutline(BaseModel):
    """A single chapter's place in the outline."""

    model_config = ConfigDict(frozen=True)

    chapter_number: int = Field(ge=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    cliffhanger: str = Field(min_length=1)


class StoryOutline(BaseModel):
    """A complete outline for a story."""

    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1)
    genre: str = Field(min_length=1)
    world_setting: str = Field(min_length=1)
    cultivation_system: str = Field(min_length=1)
    main_character: str = Field(min_length=1)
    supporting_characters: list[str] = Field(min_length=1)
    antagonist: str = Field(min_length=1)
    story_arc: str = Field(min_length=1)
    ending: str = Field(min_length=1)
    chapter_outlines: list[ChapterOutline] = Field(min_length=1)
