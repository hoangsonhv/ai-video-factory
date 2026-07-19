"""Tests for the story-outline domain value objects."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_video_factory.domain.value_objects.outline import ChapterOutline, StoryOutline


def _valid_outline(chapters: int = 2) -> dict[str, object]:
    return {
        "title": "T",
        "genre": "xianxia",
        "world_setting": "W",
        "cultivation_system": "C",
        "main_character": "M",
        "supporting_characters": ["A", "B"],
        "antagonist": "X",
        "story_arc": "arc",
        "ending": "end",
        "chapter_outlines": [
            {"chapter_number": i, "title": f"C{i}", "summary": "s", "cliffhanger": "!"}
            for i in range(1, chapters + 1)
        ],
    }


def test_valid_outline() -> None:
    outline = StoryOutline.model_validate(_valid_outline(3))
    assert len(outline.chapter_outlines) == 3
    assert outline.chapter_outlines[0].chapter_number == 1


def test_outline_is_frozen() -> None:
    outline = StoryOutline.model_validate(_valid_outline())
    with pytest.raises(ValidationError):
        outline.title = "X"  # type: ignore[misc]


def test_missing_field_raises() -> None:
    data = _valid_outline()
    del data["antagonist"]
    with pytest.raises(ValidationError):
        StoryOutline.model_validate(data)


def test_empty_value_raises() -> None:
    data = _valid_outline()
    data["title"] = ""
    with pytest.raises(ValidationError):
        StoryOutline.model_validate(data)


def test_empty_supporting_characters_raises() -> None:
    data = _valid_outline()
    data["supporting_characters"] = []
    with pytest.raises(ValidationError):
        StoryOutline.model_validate(data)


def test_chapter_number_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        ChapterOutline(chapter_number=0, title="T", summary="s", cliffhanger="!")
