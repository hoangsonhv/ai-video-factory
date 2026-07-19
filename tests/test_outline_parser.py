"""Tests for the story-outline JSON parser."""

from __future__ import annotations

import json

import pytest

from ai_video_factory.infrastructure.story.errors import OutlineParseError
from ai_video_factory.infrastructure.story.outline_parser import parse_outline


def _outline_json(chapters: int) -> str:
    return json.dumps(
        {
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
    )


def test_parse_valid_outline() -> None:
    outline = parse_outline(_outline_json(5), expected_chapters=5)
    assert outline.title == "T"
    assert len(outline.chapter_outlines) == 5


def test_invalid_json_raises() -> None:
    with pytest.raises(OutlineParseError):
        parse_outline("not json", expected_chapters=5)


def test_non_object_raises() -> None:
    with pytest.raises(OutlineParseError):
        parse_outline(json.dumps([1, 2, 3]), expected_chapters=5)


def test_missing_field_raises() -> None:
    data = json.loads(_outline_json(2))
    del data["ending"]
    with pytest.raises(OutlineParseError):
        parse_outline(json.dumps(data), expected_chapters=2)


def test_wrong_chapter_count_raises() -> None:
    with pytest.raises(OutlineParseError):
        parse_outline(_outline_json(3), expected_chapters=10)
