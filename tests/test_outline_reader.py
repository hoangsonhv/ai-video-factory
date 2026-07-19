"""Tests for reading a saved story outline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_video_factory.infrastructure.story.errors import OutlineParseError
from ai_video_factory.infrastructure.story.reader import read_outline


def _outline() -> dict[str, object]:
    return {
        "title": "T",
        "genre": "xianxia",
        "world_setting": "W",
        "cultivation_system": "C",
        "main_character": "M",
        "supporting_characters": ["A"],
        "antagonist": "X",
        "story_arc": "arc",
        "ending": "end",
        "chapter_outlines": [
            {"chapter_number": 1, "title": "C1", "summary": "s", "cliffhanger": "!"}
        ],
    }


def test_read_valid_outline(tmp_path: Path) -> None:
    path = tmp_path / "outline.json"
    path.write_text(json.dumps(_outline()), encoding="utf-8")
    outline = read_outline(path)
    assert outline.title == "T"


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(OutlineParseError):
        read_outline(tmp_path / "nope.json")


def test_invalid_schema_raises(tmp_path: Path) -> None:
    path = tmp_path / "outline.json"
    path.write_text(json.dumps({"title": "T"}), encoding="utf-8")
    with pytest.raises(OutlineParseError):
        read_outline(path)
