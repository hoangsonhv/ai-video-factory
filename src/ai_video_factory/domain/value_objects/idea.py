"""Story-idea value objects (domain layer).

Pure, immutable models with no I/O or framework coupling (docs/ai-tool.md §2.1).
``IdeaBrief`` is the generation input; ``StoryIdea`` is a generated idea.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class IdeaBrief(BaseModel):
    """The inputs that describe what story ideas to generate."""

    model_config = ConfigDict(frozen=True)

    topic: str = Field(min_length=1)
    style: str = Field(min_length=1)
    target_platform: str = Field(min_length=1)
    language: str = Field(min_length=1)


class StoryIdea(BaseModel):
    """A single generated story idea."""

    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1)
    hook: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
