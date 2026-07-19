"""Tests for the story-idea domain value objects."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_video_factory.domain.value_objects.idea import IdeaBrief, StoryIdea


def test_story_idea_fields() -> None:
    idea = StoryIdea(title="T", hook="H", summary="S", tags=["a", "b"])
    assert idea.title == "T"
    assert idea.tags == ["a", "b"]


def test_story_idea_is_frozen() -> None:
    idea = StoryIdea(title="T", hook="H", summary="S", tags=[])
    with pytest.raises(ValidationError):
        idea.title = "X"  # type: ignore[misc]


def test_story_idea_requires_non_empty_title() -> None:
    with pytest.raises(ValidationError):
        StoryIdea(title="", hook="H", summary="S", tags=[])


def test_idea_brief_fields() -> None:
    brief = IdeaBrief(topic="Tu tiên", style="Trung Quốc", target_platform="tiktok", language="vi")
    assert brief.target_platform == "tiktok"
    assert brief.language == "vi"


def test_idea_brief_rejects_empty_field() -> None:
    with pytest.raises(ValidationError):
        IdeaBrief(topic="", style="s", target_platform="tiktok", language="vi")
