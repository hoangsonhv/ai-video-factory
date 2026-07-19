"""Tests for the lenient JSON loader used by the structured-output parsers."""

from __future__ import annotations

import json

import pytest

from ai_video_factory.infrastructure.story.json_extract import loads_json


def test_plain_json() -> None:
    assert loads_json('{"a": 1}') == {"a": 1}


def test_strips_json_fence() -> None:
    assert loads_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_strips_bare_fence() -> None:
    assert loads_json("```\n[1, 2, 3]\n```") == [1, 2, 3]


def test_tolerates_surrounding_whitespace() -> None:
    assert loads_json('  \n{"a": 1}\n  ') == {"a": 1}


def test_invalid_json_raises() -> None:
    with pytest.raises(json.JSONDecodeError):
        loads_json("not json")
