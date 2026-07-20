"""Tests for FfmpegVideoComposer (mocked ffmpeg execution — no ffmpeg needed)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ai_video_factory.errors import MediaError
from ai_video_factory.infrastructure.asset_pipeline.models import AssetResult
from ai_video_factory.infrastructure.config.settings import VideoSettings
from ai_video_factory.infrastructure.video.ffmpeg_composer import (
    FfmpegVideoComposer,
    default_ffmpeg_runner,
)

_SRT = (
    "1\n00:00:00,000 --> 00:00:02,000\nA\n\n"
    "2\n00:00:02,000 --> 00:00:04,000\nB\n\n"
    "3\n00:00:04,000 --> 00:00:06,000\nC\n"
)


class _Runner:
    """Captures the command and returns a scripted sequence of (code, stderr)."""

    def __init__(self, results: list[tuple[int, str]]) -> None:
        self._results = list(results)
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str]) -> tuple[int, str]:
        self.commands.append(command)
        return self._results.pop(0)


def _assets(
    tmp_path: Path, *, image_count: int = 3
) -> tuple[AssetResult, AssetResult, AssetResult]:
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    for i in range(1, image_count + 1):
        (images_dir / f"{i:03d}.png").write_bytes(b"PNG")
    audio = tmp_path / "narration.mp3"
    audio.write_bytes(b"MP3")
    subtitle = tmp_path / "narration.srt"
    subtitle.write_text(_SRT, encoding="utf-8")
    return (
        AssetResult(success=True, path=images_dir),
        AssetResult(success=True, path=audio),
        AssetResult(success=True, path=subtitle),
    )


def _composer(tmp_path: Path, runner: _Runner, **overrides: object) -> FfmpegVideoComposer:
    settings = VideoSettings(**overrides)
    return FfmpegVideoComposer(settings, tmp_path / "video" / "final.mp4", runner=runner)


def test_compose_succeeds_and_returns_metadata(tmp_path: Path) -> None:
    runner = _Runner([(0, "")])
    composer = _composer(tmp_path, runner)

    result = asyncio.run(composer.compose_video(*_assets(tmp_path)))

    assert result.success is True
    assert result.path == tmp_path / "video" / "final.mp4"
    assert result.metadata["resolution"] == "1080x1920"
    assert result.metadata["fps"] == 30
    assert result.metadata["image_count"] == 3
    assert result.metadata["subtitle_count"] == 3
    assert result.duration == 6.0
    assert (tmp_path / "video").is_dir()  # output dir created
    assert len(runner.commands) == 1


def test_retries_once_on_temporary_failure(tmp_path: Path) -> None:
    runner = _Runner([(1, "temporary glitch"), (0, "")])
    composer = _composer(tmp_path, runner, retry_count=1)

    result = asyncio.run(composer.compose_video(*_assets(tmp_path)))

    assert result.success is True
    assert len(runner.commands) == 2  # initial attempt + one retry


def test_raises_media_error_after_persistent_failure(tmp_path: Path) -> None:
    runner = _Runner([(1, "boom"), (1, "boom again")])
    composer = _composer(tmp_path, runner, retry_count=1)

    with pytest.raises(MediaError):
        asyncio.run(composer.compose_video(*_assets(tmp_path)))
    assert len(runner.commands) == 2  # retry_count=1 -> two attempts, then give up


def test_reuses_last_image_when_fewer_images_than_cues(tmp_path: Path) -> None:
    runner = _Runner([(0, "")])
    composer = _composer(tmp_path, runner)

    asyncio.run(composer.compose_video(*_assets(tmp_path, image_count=1)))

    command = runner.commands[0]
    only_image = str(tmp_path / "images" / "001.png")
    assert command.count(only_image) == 3  # reused for all three cues


def test_missing_images_raises(tmp_path: Path) -> None:
    runner = _Runner([(0, "")])
    composer = _composer(tmp_path, runner)
    images, audio, subtitle = _assets(tmp_path)
    for png in (images.path or tmp_path).glob("*.png"):
        png.unlink()

    with pytest.raises(MediaError, match="no images"):
        asyncio.run(composer.compose_video(images, audio, subtitle))


def test_missing_cues_raises(tmp_path: Path) -> None:
    runner = _Runner([(0, "")])
    composer = _composer(tmp_path, runner)
    images, audio, subtitle = _assets(tmp_path)
    assert subtitle.path is not None
    subtitle.path.write_text("no timings here", encoding="utf-8")

    with pytest.raises(MediaError, match="no subtitle cues"):
        asyncio.run(composer.compose_video(images, audio, subtitle))


def test_default_runner_raises_media_error_when_ffmpeg_missing() -> None:
    # A binary that does not exist -> FileNotFoundError -> MediaError (graceful).
    with pytest.raises(MediaError, match="not found"):
        default_ffmpeg_runner(["this-ffmpeg-binary-does-not-exist-xyz", "-version"])
