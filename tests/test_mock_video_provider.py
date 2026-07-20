"""Tests for the development mock video provider (ffmpeg is never invoked)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ai_video_factory.errors import MediaError
from ai_video_factory.infrastructure.config.settings import VideoProviderSettings, VideoSettings
from ai_video_factory.infrastructure.diagnostics import CheckResult
from ai_video_factory.infrastructure.video.providers.base.models import (
    VideoGenerationRequest,
    VideoJobStatus,
)
from ai_video_factory.infrastructure.video.providers.errors import VideoProviderError
from ai_video_factory.infrastructure.video.providers.mock import provider as mock_module
from ai_video_factory.infrastructure.video.providers.mock.clip_command import build_clip_command
from ai_video_factory.infrastructure.video.providers.mock.provider import (
    MockVideoProvider,
    clip_filename,
)
from ai_video_factory.shared.health import HealthStatus


class _RecordingRunner:
    """Stands in for ffmpeg; records the argv it was handed."""

    def __init__(self, *return_codes: int) -> None:
        self._codes = list(return_codes) or [0]
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str]) -> tuple[int, str]:
        self.commands.append(command)
        code = self._codes[min(len(self.commands) - 1, len(self._codes) - 1)]
        return code, "" if code == 0 else "ffmpeg boom"


def _provider(
    tmp_path: Path,
    runner: _RecordingRunner | None = None,
    *,
    retry_count: int = 1,
    timeout: float = 300.0,
) -> MockVideoProvider:
    return MockVideoProvider(
        VideoProviderSettings(retry_count=retry_count, timeout=timeout),
        VideoSettings(),
        tmp_path / "video_clips",
        runner=runner or _RecordingRunner(0),
    )


def _request(scene_id: int = 1, **overrides: object) -> VideoGenerationRequest:
    defaults: dict[str, object] = {
        "scene_id": scene_id,
        "clip_id": scene_id,
        "prompt": "a cliff",
        "duration": 4.0,
    }
    defaults.update(overrides)
    return VideoGenerationRequest.model_validate(defaults)


# --- clip command (pure) ---------------------------------------------------


def test_clip_command_from_a_colour_source_when_there_is_no_image(tmp_path: Path) -> None:
    command = build_clip_command(
        output_path=tmp_path / "shot_001.mp4", duration=4.0, settings=VideoSettings()
    )

    assert command[0] == "ffmpeg"
    assert "lavfi" in command
    assert any("color=c=black:s=1080x1920" in arg for arg in command)
    assert command[-1].endswith("shot_001.mp4")


def test_clip_command_loops_the_reference_image_when_given(tmp_path: Path) -> None:
    image = tmp_path / "001.png"
    command = build_clip_command(
        output_path=tmp_path / "shot_001.mp4",
        duration=4.0,
        settings=VideoSettings(),
        reference_image=image,
    )

    assert "-loop" in command
    assert str(image) in command
    assert any("crop=1080:1920" in arg for arg in command)


def test_clip_command_honours_the_video_settings(tmp_path: Path) -> None:
    settings = VideoSettings(width=720, height=1280, fps=24, video_codec="libx265")
    command = build_clip_command(
        output_path=tmp_path / "shot_001.mp4", duration=2.0, settings=settings
    )

    assert "libx265" in command
    assert "24" in command
    assert any("720x1280" in arg for arg in command)


def test_clip_command_rejects_a_non_positive_duration(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="duration must be positive"):
        build_clip_command(output_path=tmp_path / "x.mp4", duration=0.0, settings=VideoSettings())


# --- naming ----------------------------------------------------------------


def test_clip_filenames_are_zero_padded() -> None:
    assert clip_filename(1) == "shot_001.mp4"
    assert clip_filename(12) == "shot_012.mp4"
    assert clip_filename(345) == "shot_345.mp4"


# --- generation ------------------------------------------------------------


def test_generate_returns_a_completed_result(tmp_path: Path) -> None:
    provider = _provider(tmp_path)

    result = asyncio.run(provider.generate(_request(2)))

    assert result.status is VideoJobStatus.COMPLETED
    assert result.is_completed
    assert result.scene_id == 2
    assert result.provider == "mock"
    assert result.model == "mock-slideshow"
    assert result.video_path == tmp_path / "video_clips" / "shot_002.mp4"
    assert result.duration == 4.0
    assert result.remote_job_id is None
    assert result.metadata["mock"] is True
    assert result.metadata["resolution"] == "1080x1920"


def test_generate_creates_the_output_directory(tmp_path: Path) -> None:
    asyncio.run(_provider(tmp_path).generate(_request()))

    assert (tmp_path / "video_clips").is_dir()


def test_generate_uses_an_existing_reference_image(tmp_path: Path) -> None:
    image = tmp_path / "001.png"
    image.write_bytes(b"png")
    runner = _RecordingRunner(0)

    result = asyncio.run(_provider(tmp_path, runner).generate(_request(reference_images=(image,))))

    assert str(image) in runner.commands[0]
    assert result.metadata["source"] == "reference_image"


def test_generate_ignores_a_missing_reference_image(tmp_path: Path) -> None:
    runner = _RecordingRunner(0)

    result = asyncio.run(
        _provider(tmp_path, runner).generate(_request(reference_images=(tmp_path / "nope.png",)))
    )

    assert result.metadata["source"] == "color"
    assert "lavfi" in runner.commands[0]


def test_generate_retries_then_succeeds(tmp_path: Path) -> None:
    runner = _RecordingRunner(1, 0)

    result = asyncio.run(_provider(tmp_path, runner, retry_count=1).generate(_request()))

    assert len(runner.commands) == 2
    assert result.is_completed


def test_generate_raises_after_every_attempt_fails(tmp_path: Path) -> None:
    runner = _RecordingRunner(1, 1)

    with pytest.raises(VideoProviderError, match="after 2 attempt"):
        asyncio.run(_provider(tmp_path, runner, retry_count=1).generate(_request()))

    assert len(runner.commands) == 2


def test_generate_without_retries_attempts_once(tmp_path: Path) -> None:
    runner = _RecordingRunner(1)

    with pytest.raises(VideoProviderError):
        asyncio.run(_provider(tmp_path, runner, retry_count=0).generate(_request()))

    assert len(runner.commands) == 1


def test_generate_translates_a_missing_ffmpeg_binary(tmp_path: Path) -> None:
    def _missing(command: list[str]) -> tuple[int, str]:
        raise MediaError("ffmpeg executable not found")

    provider = MockVideoProvider(
        VideoProviderSettings(), VideoSettings(), tmp_path, runner=_missing
    )

    with pytest.raises(VideoProviderError, match="ffmpeg executable not found"):
        asyncio.run(provider.generate(_request()))


def test_generate_translates_a_timeout(tmp_path: Path) -> None:
    def _slow(command: list[str]) -> tuple[int, str]:
        import time

        time.sleep(0.5)
        return 0, ""

    provider = MockVideoProvider(
        VideoProviderSettings(timeout=0.01), VideoSettings(), tmp_path, runner=_slow
    )

    with pytest.raises(VideoProviderError, match="timed out"):
        asyncio.run(provider.generate(_request()))


# --- contract & health -----------------------------------------------------


def test_supported_models(tmp_path: Path) -> None:
    assert _provider(tmp_path).supported_models() == ["mock-slideshow"]
    assert _provider(tmp_path).name == "mock"


def test_health_check_warns_that_it_is_a_development_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        mock_module,
        "check_ffmpeg",
        lambda: CheckResult(name="FFmpeg", status=HealthStatus.OK, detail="7.0"),
    )

    health = asyncio.run(_provider(tmp_path).health_check())

    assert health.status is HealthStatus.WARN
    assert "not AI video" in health.detail


def test_health_check_fails_without_ffmpeg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mock_module,
        "check_ffmpeg",
        lambda: CheckResult(name="FFmpeg", status=HealthStatus.FAIL, detail="not found on PATH"),
    )

    health = asyncio.run(_provider(tmp_path).health_check())

    assert health.status is HealthStatus.FAIL
    assert "ffmpeg" in health.detail
