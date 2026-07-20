"""Tests for the Gemini transcription reply parser (no SDK / network)."""

from __future__ import annotations

import json

import pytest

from ai_video_factory.infrastructure.providers.base.errors import InvalidResponseError
from ai_video_factory.infrastructure.providers.transcription.gemini.client import parse_segments


def test_parses_json_array() -> None:
    payload = json.dumps(
        [
            {"start": 0.0, "end": 2.0, "text": "Xin chào"},
            {"start": 2.0, "end": 4.0, "text": "Thế giới"},
        ]
    )
    segments = parse_segments(payload)
    assert len(segments) == 2
    assert segments[0].text == "Xin chào"
    assert segments[1].end == 4.0


def test_parses_object_with_segments_key() -> None:
    payload = json.dumps({"segments": [{"start": 1, "end": 3, "text": "Một"}]})
    segments = parse_segments(payload)
    assert segments[0].start == 1.0


def test_skips_empty_text_entries() -> None:
    payload = json.dumps(
        [{"start": 0, "end": 1, "text": "  "}, {"start": 1, "end": 2, "text": "kept"}]
    )
    segments = parse_segments(payload)
    assert [s.text for s in segments] == ["kept"]


def test_invalid_json_raises() -> None:
    with pytest.raises(InvalidResponseError):
        parse_segments("not json {")


def test_empty_list_raises() -> None:
    with pytest.raises(InvalidResponseError):
        parse_segments("[]")


def test_end_before_start_is_clamped() -> None:
    # A model that returns end < start still yields a valid (non-negative) segment.
    payload = json.dumps([{"start": 5.0, "end": 3.0, "text": "oops"}])
    segments = parse_segments(payload)
    assert segments[0].end >= segments[0].start
