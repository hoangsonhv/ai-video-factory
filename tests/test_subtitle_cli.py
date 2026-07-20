"""Tests for the ``ai-video-factory subtitle`` CLI command (no real API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.infrastructure.providers.transcription.base.models import (
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionSegment,
)
from ai_video_factory.interface.cli import subtitle_commands as sc
from ai_video_factory.interface.cli.app import app

runner = CliRunner()


class _FakeTranscriptionProvider:
    def __init__(self, segments: list[TranscriptionSegment]) -> None:
        self._segments = segments

    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        return TranscriptionResult(
            segments=tuple(self._segments), provider="fake", language=request.language
        )


def _use_fake(monkeypatch: pytest.MonkeyPatch, segments: list[TranscriptionSegment]) -> None:
    monkeypatch.setattr(
        sc.TranscriptionProviderFactory,
        "create",
        lambda settings: _FakeTranscriptionProvider(segments),
    )


def _write_chapter(path: Path) -> None:
    path.write_text(
        json.dumps({"title": "T", "content": "Xin chào thế giới", "estimated_duration_seconds": 5}),
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))


def test_subtitle_command_generates_srt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_fake(
        monkeypatch,
        [
            TranscriptionSegment(start=0.0, end=2.0, text="Xin chào"),
            TranscriptionSegment(start=2.0, end=4.0, text="Thế giới"),
        ],
    )
    audio = tmp_path / "narration.mp3"
    audio.write_bytes(b"AUDIO")
    chapter = tmp_path / "chapter.json"
    _write_chapter(chapter)

    result = runner.invoke(app, ["subtitle", "--audio", str(audio), "--chapter", str(chapter)])

    assert result.exit_code == 0
    srt_path = tmp_path / "out" / "subtitles" / "narration.srt"
    assert srt_path.exists()
    content = srt_path.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:02,500" not in content  # ends at 2.0, not 2.5
    assert "1\n00:00:00,000 --> 00:00:02,000\nXin chào" in content
    assert "Thế giới" in content  # Vietnamese preserved


def test_subtitle_command_missing_audio_fails(tmp_path: Path) -> None:
    chapter = tmp_path / "chapter.json"
    _write_chapter(chapter)
    result = runner.invoke(
        app, ["subtitle", "--audio", str(tmp_path / "nope.mp3"), "--chapter", str(chapter)]
    )
    assert result.exit_code == 1


def test_subtitle_command_missing_chapter_fails(tmp_path: Path) -> None:
    audio = tmp_path / "narration.mp3"
    audio.write_bytes(b"AUDIO")
    result = runner.invoke(
        app, ["subtitle", "--audio", str(audio), "--chapter", str(tmp_path / "nope.json")]
    )
    assert result.exit_code == 1


def test_subtitle_command_skips_when_exists_without_force(tmp_path: Path) -> None:
    # Pre-existing subtitle and no provider wired: skip returns before building it.
    subtitles_dir = tmp_path / "out" / "subtitles"
    subtitles_dir.mkdir(parents=True)
    (subtitles_dir / "narration.srt").write_text("OLD", encoding="utf-8")
    audio = tmp_path / "narration.mp3"
    audio.write_bytes(b"AUDIO")
    chapter = tmp_path / "chapter.json"
    _write_chapter(chapter)

    result = runner.invoke(app, ["subtitle", "--audio", str(audio), "--chapter", str(chapter)])

    assert result.exit_code == 0
    assert "Skipped" in result.stdout
    assert (subtitles_dir / "narration.srt").read_text(encoding="utf-8") == "OLD"


def test_subtitle_command_force_regenerates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_fake(monkeypatch, [TranscriptionSegment(start=0.0, end=1.0, text="Mới")])
    subtitles_dir = tmp_path / "out" / "subtitles"
    subtitles_dir.mkdir(parents=True)
    (subtitles_dir / "narration.srt").write_text("OLD", encoding="utf-8")
    audio = tmp_path / "narration.mp3"
    audio.write_bytes(b"AUDIO")
    chapter = tmp_path / "chapter.json"
    _write_chapter(chapter)

    result = runner.invoke(
        app, ["subtitle", "--audio", str(audio), "--chapter", str(chapter), "--force"]
    )

    assert result.exit_code == 0
    assert "Mới" in (subtitles_dir / "narration.srt").read_text(encoding="utf-8")
