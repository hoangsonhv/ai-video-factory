"""Tests for the ``ai-video-factory tts`` CLI command (no real API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.infrastructure.media.audio_storage import AudioStorage
from ai_video_factory.infrastructure.providers.speech.base.models import (
    SpeechSynthesisRequest,
    SpeechSynthesisResponse,
)
from ai_video_factory.interface.cli import tts_commands as tts
from ai_video_factory.interface.cli.app import app

runner = CliRunner()


class _FakeSpeechProvider:
    """Uses the real storage to actually save bytes, so a file is produced."""

    def __init__(self, storage: AudioStorage) -> None:
        self._storage = storage

    async def synthesize(self, request: SpeechSynthesisRequest) -> SpeechSynthesisResponse:
        path = self._storage.save(b"FAKEWAV")
        return SpeechSynthesisResponse(
            audio_path=path,
            provider="fake",
            voice="Kore",
            duration_seconds=4.2,
            sample_rate=24000,
        )


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))


def test_tts_command_synthesizes_and_saves(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        tts.SpeechProviderFactory, "create", lambda settings, storage: _FakeSpeechProvider(storage)
    )
    chapter_path = tmp_path / "chapter.json"
    chapter_path.write_text(
        json.dumps({"title": "T", "content": "Xin chào", "estimated_duration_seconds": 5}),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["tts", "--chapter", str(chapter_path)])

    assert result.exit_code == 0
    audio_dir = tmp_path / "out" / "audio"
    assert (audio_dir / "narration.mp3").exists()
    metadata_path = audio_dir / "metadata.json"
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata == {
        "duration": 4.2,
        "voice": "Kore",
        "provider": "fake",
        "sample_rate": 24000,
    }


def test_tts_command_missing_chapter_fails(tmp_path: Path) -> None:
    result = runner.invoke(app, ["tts", "--chapter", str(tmp_path / "nope.json")])
    assert result.exit_code == 1


def _write_chapter(path: Path) -> None:
    path.write_text(
        json.dumps({"title": "T", "content": "Xin chào", "estimated_duration_seconds": 5}),
        encoding="utf-8",
    )


def test_tts_skips_when_output_exists_without_force(tmp_path: Path) -> None:
    # Pre-existing narration and no provider wired: if skip works the provider is
    # never built, so no API key is needed and the file is left untouched.
    audio_dir = tmp_path / "out" / "audio"
    audio_dir.mkdir(parents=True)
    (audio_dir / "narration.mp3").write_bytes(b"OLD")
    chapter_path = tmp_path / "chapter.json"
    _write_chapter(chapter_path)

    result = runner.invoke(app, ["tts", "--chapter", str(chapter_path)])

    assert result.exit_code == 0
    assert "Skipped" in result.stdout
    assert (audio_dir / "narration.mp3").read_bytes() == b"OLD"


def test_tts_force_regenerates_existing_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        tts.SpeechProviderFactory, "create", lambda settings, storage: _FakeSpeechProvider(storage)
    )
    audio_dir = tmp_path / "out" / "audio"
    audio_dir.mkdir(parents=True)
    (audio_dir / "narration.mp3").write_bytes(b"OLD")
    chapter_path = tmp_path / "chapter.json"
    _write_chapter(chapter_path)

    result = runner.invoke(app, ["tts", "--chapter", str(chapter_path), "--force"])

    assert result.exit_code == 0
    assert (audio_dir / "narration.mp3").read_bytes() == b"FAKEWAV"
