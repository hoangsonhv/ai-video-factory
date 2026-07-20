"""Tests for the ``ai-video-factory video`` CLI commands (ffmpeg is never run)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.domain.value_objects.movie import Camera, Movie, Scene
from ai_video_factory.infrastructure.diagnostics import CheckResult
from ai_video_factory.infrastructure.video.providers.mock import provider as mock_module
from ai_video_factory.interface.cli.app import app
from ai_video_factory.shared.health import HealthStatus

runner = CliRunner()


def _movie(scene_count: int = 2) -> Movie:
    return Movie(
        title="Tu Tiên",
        style="cinematic",
        duration=60,
        scenes=tuple(
            Scene(
                id=index,
                duration=4,
                camera=Camera(shot="wide"),
                image_prompt=f"scene {index} image",
                video_prompt=f"scene {index} video",
            )
            for index in range(1, scene_count + 1)
        ),
    )


def _write_movie(path: Path, movie: Movie | None = None) -> Path:
    path.write_text(
        json.dumps((movie or _movie()).model_dump(), ensure_ascii=False), encoding="utf-8"
    )
    return path


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))


@pytest.fixture
def _ffmpeg_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mock_module,
        "check_ffmpeg",
        lambda: CheckResult(name="FFmpeg", status=HealthStatus.OK, detail="7.0"),
    )


@pytest.fixture
def _ffmpeg_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mock_module,
        "check_ffmpeg",
        lambda: CheckResult(name="FFmpeg", status=HealthStatus.FAIL, detail="not found on PATH"),
    )


def _fake_runner(monkeypatch: pytest.MonkeyPatch, *, return_code: int = 0) -> list[list[str]]:
    """Replace the ffmpeg runner the mock provider defaults to."""
    commands: list[list[str]] = []

    def _run(command: list[str]) -> tuple[int, str]:
        commands.append(command)
        if return_code == 0:
            Path(command[-1]).write_bytes(b"fake mp4")
        return return_code, "" if return_code == 0 else "boom"

    monkeypatch.setattr(mock_module, "default_ffmpeg_runner", _run)
    return commands


# --- video providers -------------------------------------------------------


def test_providers_lists_the_mock_and_marks_it_default(_ffmpeg_ok: None) -> None:
    result = runner.invoke(app, ["video", "providers"])

    assert result.exit_code == 0
    assert "mock" in result.stdout
    assert "mock-slideshow" in result.stdout


def test_providers_integrates_no_unapproved_provider(_ffmpeg_ok: None) -> None:
    """Kling was approved in Sprint 021; the rest still are not."""
    result = runner.invoke(app, ["video", "providers"])

    lowered = result.stdout.lower()
    for forbidden in ("veo", "runway", "hailuo", "sora"):
        assert forbidden not in lowered


def test_providers_fails_when_the_configured_provider_is_unregistered(
    monkeypatch: pytest.MonkeyPatch, _ffmpeg_ok: None
) -> None:
    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__PROVIDER", "veo")

    result = runner.invoke(app, ["video", "providers"])

    assert result.exit_code == 1
    assert "not registered" in result.stdout


# --- video doctor ----------------------------------------------------------


def test_doctor_reports_the_mock_as_a_development_provider(_ffmpeg_ok: None) -> None:
    result = runner.invoke(app, ["video", "doctor"])

    assert result.exit_code == 0
    assert "WARN" in result.stdout


def test_doctor_ignores_an_unconfigured_alternative_driver(_ffmpeg_ok: None) -> None:
    """Kling has no API key here, but `mock` is the configured default — exit 0."""
    result = runner.invoke(app, ["video", "doctor"])

    assert result.exit_code == 0
    assert "kling" in result.stdout  # still reported, just not fatal


def test_doctor_fails_when_ffmpeg_is_missing(_ffmpeg_missing: None) -> None:
    result = runner.invoke(app, ["video", "doctor"])

    assert result.exit_code == 1
    assert "FAIL" in result.stdout


# --- video generate --------------------------------------------------------


def test_generate_writes_one_clip_per_scene(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _ffmpeg_ok: None
) -> None:
    commands = _fake_runner(monkeypatch)
    scene_file = _write_movie(tmp_path / "movie_consistent.json")

    result = runner.invoke(app, ["video", "generate", "--scene", str(scene_file)])

    assert result.exit_code == 0
    clips = tmp_path / "out" / "video_clips"
    assert (clips / "shot_001.mp4").exists()
    assert (clips / "shot_002.mp4").exists()
    assert len(commands) == 2
    assert "Generated 2 clip(s), 0 failed" in result.stdout


def test_generate_passes_the_scene_duration_to_ffmpeg(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _ffmpeg_ok: None
) -> None:
    commands = _fake_runner(monkeypatch)
    _write_movie(tmp_path / "movie_consistent.json")

    runner.invoke(app, ["video", "generate", "--scene", str(tmp_path / "movie_consistent.json")])

    assert "4.000" in commands[0]


def test_generate_continues_past_a_failed_scene_and_exits_non_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _ffmpeg_ok: None
) -> None:
    commands = _fake_runner(monkeypatch, return_code=1)
    scene_file = _write_movie(tmp_path / "movie_consistent.json")

    result = runner.invoke(app, ["video", "generate", "--scene", str(scene_file)])

    assert result.exit_code == 1
    assert "0 clip(s), 2 failed" in result.stdout
    assert len(commands) == 4  # two scenes, each attempted twice (retry_count=1)


def test_generate_fails_when_the_provider_is_not_ready(
    tmp_path: Path, _ffmpeg_missing: None
) -> None:
    scene_file = _write_movie(tmp_path / "movie_consistent.json")

    result = runner.invoke(app, ["video", "generate", "--scene", str(scene_file)])

    assert result.exit_code == 1
    assert "not ready" in result.stdout
    assert not (tmp_path / "out" / "video_clips").exists()


def test_generate_missing_scene_file_fails(tmp_path: Path, _ffmpeg_ok: None) -> None:
    result = runner.invoke(app, ["video", "generate", "--scene", str(tmp_path / "nope.json")])

    assert result.exit_code == 1
    assert "scene file not found" in result.stdout


def test_generate_rejects_a_movie_without_scenes(tmp_path: Path, _ffmpeg_ok: None) -> None:
    scene_file = _write_movie(tmp_path / "movie.json", _movie(scene_count=0))

    result = runner.invoke(app, ["video", "generate", "--scene", str(scene_file)])

    assert result.exit_code == 1
    assert "no scenes" in result.stdout


def test_generate_touches_no_other_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _ffmpeg_ok: None
) -> None:
    _fake_runner(monkeypatch)
    scene_file = _write_movie(tmp_path / "movie_consistent.json")

    runner.invoke(app, ["video", "generate", "--scene", str(scene_file)])

    out = tmp_path / "out"
    assert [p.name for p in out.iterdir()] == ["video_clips"]


# --- backward compatibility ------------------------------------------------


def test_the_existing_commands_still_register() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("compose", "movie", "character", "image", "tts", "subtitle", "video"):
        assert command in result.stdout
