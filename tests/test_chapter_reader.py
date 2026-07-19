"""Tests for reading a saved story chapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_video_factory.infrastructure.story.errors import ChapterParseError
from ai_video_factory.infrastructure.story.reader import read_chapter


def test_read_valid_chapter(tmp_path: Path) -> None:
    path = tmp_path / "chapter.json"
    path.write_text(
        json.dumps({"title": "T", "content": "prose", "estimated_duration_seconds": 30}),
        encoding="utf-8",
    )
    chapter = read_chapter(path)
    assert chapter.title == "T"
    assert chapter.estimated_duration_seconds == 30


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ChapterParseError):
        read_chapter(tmp_path / "nope.json")


def test_invalid_schema_raises(tmp_path: Path) -> None:
    path = tmp_path / "chapter.json"
    path.write_text(json.dumps({"title": "T"}), encoding="utf-8")
    with pytest.raises(ChapterParseError):
        read_chapter(path)
