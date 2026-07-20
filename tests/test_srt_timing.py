"""Tests for the subtitle timing parser (pure, no I/O)."""

from __future__ import annotations

from ai_video_factory.infrastructure.video.srt_timing import parse_srt_cues

_SRT = (
    "1\n00:00:00,000 --> 00:00:02,500\nXin chào\n\n"
    "2\n00:00:02,500 --> 00:00:05,000\nThế giới\n\n"
    "3\n00:01:01,250 --> 00:01:02,000\nHết\n"
)


def test_parses_all_cues_with_seconds() -> None:
    cues = parse_srt_cues(_SRT)
    assert len(cues) == 3
    assert cues[0].start == 0.0
    assert cues[0].end == 2.5
    assert cues[1].start == 2.5
    assert cues[2].start == 61.25
    assert cues[2].end == 62.0


def test_indexes_are_sequential() -> None:
    cues = parse_srt_cues(_SRT)
    assert [c.index for c in cues] == [1, 2, 3]


def test_no_timings_returns_empty() -> None:
    assert parse_srt_cues("just some text with no timestamps") == []


def test_tolerates_dot_millis_separator() -> None:
    cues = parse_srt_cues("00:00:00.000 --> 00:00:01.500\ntext")
    assert cues[0].end == 1.5
