"""Story-chapter value object (domain layer).

The full narratable prose produced from a story outline. Pure and immutable
(docs/ai-tool.md §2.1).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StoryChapter(BaseModel):
    """A complete chapter of narration prose."""

    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    estimated_duration_seconds: int = Field(gt=0)
