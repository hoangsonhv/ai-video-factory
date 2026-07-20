"""Tests for the ``ai-video-factory compose`` CLI command (no ffmpeg needed)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.infrastructure.asset_pipeline.models import AssetResult
from ai_video_factory.infrastructure.diagnostics import CheckResult
from ai_video_factory.interface.cli import compose_commands as cc
from ai_video_factory.interface.cli.app import app
from ai_video_factory.shared.health import HealthStatus

runner = CliRunner()


class _FakeComposer:
    """Stands in for FfmpegVideoComposer; writes a dummy mp4, returns metadata."""

    def __init__(self, settings: object, output_path: Path, **_: object) -> None:
        self._output = output_path

    async def compose_video(
        self, images: AssetResult, voice: AssetResult, subtitles: AssetResult
    ) -> AssetResult:
        self._output.parent.mkdir(parents=True, exist_ok=True)
        self._output.write_bytes(b"MP4")
        return AssetResult(
            success=True,
            path=self._output,
            duration=12.5,
            metadata={
                "fps": 30,
                "resolution": "1080x1920",
                "image_count": 2,
                "subtitle_count": 3,
            },
        )


def _ffmpeg_ok() -> CheckResult:
    return CheckResult(name="FFmpeg", status=HealthStatus.OK, detail="/usr/bin/ffmpeg")


def _ffmpeg_missing() -> CheckResult:
    return CheckResult(name="FFmpeg", status=HealthStatus.FAIL, detail="not found on PATH")


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    images = tmp_path / "images"
    images.mkdir()
    (images / "001.png").write_bytes(b"PNG")
    audio = tmp_path / "narration.mp3"
    audio.write_bytes(b"MP3")
    subtitle = tmp_path / "narration.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nA\n", encoding="utf-8")
    return images, audio, subtitle


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))


def test_compose_generates_video_and_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cc, "check_ffmpeg", _ffmpeg_ok)
    monkeypatch.setattr(cc, "FfmpegVideoComposer", _FakeComposer)
    images, audio, subtitle = _inputs(tmp_path)

    result = runner.invoke(
        app,
        ["compose", "--images", str(images), "--audio", str(audio), "--subtitle", str(subtitle)],
    )

    assert result.exit_code == 0
    video_dir = tmp_path / "out" / "video"
    assert (video_dir / "final.mp4").exists()
    metadata = json.loads((video_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata == {
        "duration": 12.5,
        "fps": 30,
        "resolution": "1080x1920",
        "image_count": 2,
        "subtitle_count": 3,
    }


def test_compose_fails_when_ffmpeg_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cc, "check_ffmpeg", _ffmpeg_missing)
    images, audio, subtitle = _inputs(tmp_path)

    result = runner.invoke(
        app,
        ["compose", "--images", str(images), "--audio", str(audio), "--subtitle", str(subtitle)],
    )

    assert result.exit_code == 1
    assert "FFmpeg is required" in result.stdout


def test_compose_missing_images_dir_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cc, "check_ffmpeg", _ffmpeg_ok)
    _, audio, subtitle = _inputs(tmp_path)

    result = runner.invoke(
        app,
        [
            "compose",
            "--images",
            str(tmp_path / "nope"),
            "--audio",
            str(audio),
            "--subtitle",
            str(subtitle),
        ],
    )

    assert result.exit_code == 1
    assert "images directory not found" in result.stdout


def test_compose_missing_audio_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cc, "check_ffmpeg", _ffmpeg_ok)
    images, _, subtitle = _inputs(tmp_path)

    result = runner.invoke(
        app,
        [
            "compose",
            "--images",
            str(images),
            "--audio",
            str(tmp_path / "nope.mp3"),
            "--subtitle",
            str(subtitle),
        ],
    )

    assert result.exit_code == 1
    assert "audio file not found" in result.stdout
