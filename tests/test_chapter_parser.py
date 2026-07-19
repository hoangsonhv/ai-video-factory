"""Tests for the story-chapter JSON parser and duration estimator."""

from __future__ import annotations

import json

import pytest

from ai_video_factory.infrastructure.story.chapter_parser import (
    estimate_duration_seconds,
    parse_chapter,
)
from ai_video_factory.infrastructure.story.errors import ChapterParseError


def test_estimate_duration_scales_with_words() -> None:
    text = " ".join(["word"] * 150)
    assert estimate_duration_seconds(text, words_per_minute=150) == 60


def test_estimate_duration_non_empty_is_at_least_one() -> None:
    assert estimate_duration_seconds("one", words_per_minute=150) == 1


def test_estimate_duration_empty_is_zero() -> None:
    assert estimate_duration_seconds("", words_per_minute=150) == 0


def test_parse_valid_chapter_computes_duration() -> None:
    content = json.dumps({"title": "T", "content": " ".join(["w"] * 300)})
    chapter = parse_chapter(content, words_per_minute=150)
    assert chapter.title == "T"
    assert chapter.estimated_duration_seconds == 120


def test_parse_invalid_json_raises() -> None:
    with pytest.raises(ChapterParseError):
        parse_chapter("not json")


def test_parse_non_object_raises() -> None:
    with pytest.raises(ChapterParseError):
        parse_chapter(json.dumps(["a", "b"]))


def test_parse_empty_content_raises() -> None:
    with pytest.raises(ChapterParseError):
        parse_chapter(json.dumps({"title": "T", "content": ""}))


# --- Regression: robustness fixes for the chapter JSON bug ---


def test_parse_tolerates_markdown_fences() -> None:
    content = "```json\n" + json.dumps({"title": "T", "content": "some prose"}) + "\n```"
    assert parse_chapter(content).content == "some prose"


def test_parse_tolerates_unescaped_control_characters() -> None:
    # A literal newline inside the JSON string value would fail strict json.loads
    # ("Invalid control character"); the chapter parser tolerates it.
    content = '{"title": "T", "content": "First line.\nSecond line has words."}'
    chapter = parse_chapter(content)
    assert "\n" in chapter.content
    assert chapter.title == "T"


def test_parse_tolerates_double_encoded_json() -> None:
    inner = json.dumps({"title": "T", "content": "prose with several words here"})
    content = json.dumps(inner)  # the object encoded again as a JSON string
    assert parse_chapter(content).title == "T"


def test_parse_error_reports_actual_detail() -> None:
    with pytest.raises(ChapterParseError) as exc_info:
        parse_chapter("{ this is not json")
    message = str(exc_info.value)
    # The message surfaces the real JSONDecodeError detail (line/column), not a
    # generic "provider returned invalid JSON".
    assert "invalid JSON from provider" in message
    assert "line" in message
