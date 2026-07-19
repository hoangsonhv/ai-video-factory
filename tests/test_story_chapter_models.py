"""Tests for the story-chapter domain value object."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_video_factory.domain.value_objects.chapter import StoryChapter


def test_valid_chapter() -> None:
    chapter = StoryChapter(title="T", content="prose", estimated_duration_seconds=30)
    assert chapter.title == "T"
    assert chapter.estimated_duration_seconds == 30


def test_chapter_is_frozen() -> None:
    chapter = StoryChapter(title="T", content="prose", estimated_duration_seconds=30)
    with pytest.raises(ValidationError):
        chapter.title = "X"  # type: ignore[misc]


def test_empty_content_raises() -> None:
    with pytest.raises(ValidationError):
        StoryChapter(title="T", content="", estimated_duration_seconds=30)


def test_duration_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        StoryChapter(title="T", content="prose", estimated_duration_seconds=0)
