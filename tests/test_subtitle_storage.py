"""Tests for the subtitle filesystem storage."""

from __future__ import annotations

from pathlib import Path

from ai_video_factory.infrastructure.media.subtitle_storage import SubtitleStorage


def test_saves_utf8_srt(tmp_path: Path) -> None:
    storage = SubtitleStorage(tmp_path / "subtitles")
    path = storage.save("1\n00:00:00,000 --> 00:00:01,000\nNgười tu tiên\n")

    assert path.name == "narration.srt"
    assert path.read_text(encoding="utf-8").endswith("Người tu tiên\n")


def test_creates_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "subtitles"
    storage = SubtitleStorage(target)
    path = storage.save("data")
    assert path.exists()
    assert storage.directory == target
