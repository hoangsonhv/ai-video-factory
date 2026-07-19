"""Tests for the story-idea JSON parser."""

from __future__ import annotations

import json

import pytest

from ai_video_factory.infrastructure.story.errors import IdeaParseError
from ai_video_factory.infrastructure.story.parser import parse_ideas

_ONE = {"title": "T", "hook": "H", "summary": "S", "tags": ["a"]}


def test_parse_object_with_ideas_key() -> None:
    content = json.dumps({"ideas": [_ONE, _ONE]})
    ideas = parse_ideas(content)
    assert len(ideas) == 2
    assert ideas[0].title == "T"


def test_parse_bare_array() -> None:
    ideas = parse_ideas(json.dumps([_ONE]))
    assert len(ideas) == 1


def test_parse_tolerates_markdown_fences() -> None:
    content = "```json\n" + json.dumps({"ideas": [_ONE]}) + "\n```"
    assert len(parse_ideas(content)) == 1


def test_invalid_json_raises() -> None:
    with pytest.raises(IdeaParseError):
        parse_ideas("not json at all")


def test_missing_field_raises() -> None:
    content = json.dumps({"ideas": [{"title": "T", "hook": "H"}]})
    with pytest.raises(IdeaParseError):
        parse_ideas(content)


def test_non_list_raises() -> None:
    with pytest.raises(IdeaParseError):
        parse_ideas(json.dumps({"ideas": {"title": "T"}}))


def test_empty_ideas_raises() -> None:
    with pytest.raises(IdeaParseError):
        parse_ideas(json.dumps({"ideas": []}))
