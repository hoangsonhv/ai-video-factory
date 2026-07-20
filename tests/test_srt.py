"""Tests for the SRT formatter (pure, no I/O)."""

from __future__ import annotations

from ai_video_factory.infrastructure.providers.transcription.base.models import TranscriptionSegment
from ai_video_factory.infrastructure.providers.transcription.base.srt import to_srt


def _seg(start: float, end: float, text: str) -> TranscriptionSegment:
    return TranscriptionSegment(start=start, end=end, text=text)


def test_formats_sequential_cues_with_timestamps() -> None:
    srt = to_srt([_seg(0.0, 2.5, "Xin chào"), _seg(2.5, 5.0, "Thế giới")])
    assert srt == (
        "1\n00:00:00,000 --> 00:00:02,500\nXin chào\n\n2\n00:00:02,500 --> 00:00:05,000\nThế giới\n"
    )


def test_preserves_vietnamese_utf8() -> None:
    srt = to_srt([_seg(0.0, 1.0, "Người tu tiên đi giao hàng")])
    assert "Người tu tiên đi giao hàng" in srt


def test_renumbers_cues_from_one() -> None:
    srt = to_srt([_seg(10.0, 11.0, "a"), _seg(20.0, 21.0, "b"), _seg(30.0, 31.0, "c")])
    assert srt.startswith("1\n")
    assert "\n2\n" in srt
    assert "\n3\n" in srt


def test_formats_hours_and_millis() -> None:
    srt = to_srt([_seg(3661.25, 3662.0, "late")])
    assert "01:01:01,250 --> 01:01:02,000" in srt


def test_zero_length_segment_gets_minimal_duration() -> None:
    srt = to_srt([_seg(1.0, 1.0, "blip")])
    # end is nudged past start so the cue is valid SubRip
    assert "00:00:01,000 --> 00:00:01,001" in srt
