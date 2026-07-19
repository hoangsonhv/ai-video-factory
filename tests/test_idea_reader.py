"""Tests for reading a selected idea from an ideas JSON file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_video_factory.infrastructure.story.errors import IdeaParseError
from ai_video_factory.infrastructure.story.reader import read_idea

_IDEA = {"title": "T", "hook": "H", "summary": "S", "tags": ["a"]}


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_read_from_object_with_ideas(tmp_path: Path) -> None:
    path = tmp_path / "ideas.json"
    _write(path, {"ideas": [_IDEA, {**_IDEA, "title": "Second"}]})
    assert read_idea(path, 1).title == "Second"


def test_read_from_bare_array(tmp_path: Path) -> None:
    path = tmp_path / "ideas.json"
    _write(path, [_IDEA])
    assert read_idea(path, 0).title == "T"


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(IdeaParseError):
        read_idea(tmp_path / "nope.json", 0)


def test_index_out_of_range_raises(tmp_path: Path) -> None:
    path = tmp_path / "ideas.json"
    _write(path, {"ideas": [_IDEA]})
    with pytest.raises(IdeaParseError):
        read_idea(path, 5)


def test_invalid_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "ideas.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(IdeaParseError):
        read_idea(path, 0)
