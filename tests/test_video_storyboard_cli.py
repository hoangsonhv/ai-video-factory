"""Tests for `video generate --storyboard`: contract, references, resume, manifest."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.domain.value_objects.storyboard import Storyboard, StoryboardShot
from ai_video_factory.infrastructure.config.settings import VideoProviderSettings, VideoSettings
from ai_video_factory.infrastructure.diagnostics import CheckResult
from ai_video_factory.infrastructure.video.providers.base.models import (
    ClipReferences,
    VideoGenerationRequest,
)
from ai_video_factory.infrastructure.video.providers.base.provider import VideoProvider
from ai_video_factory.infrastructure.video.providers.mock import provider as mock_module
from ai_video_factory.infrastructure.video.providers.mock.provider import (
    MockVideoProvider,
    clip_filename,
)
from ai_video_factory.infrastructure.video.providers.storyboard_source import (
    build_requests,
    read_storyboard,
)
from ai_video_factory.interface.cli.app import app
from ai_video_factory.shared.health import HealthStatus

runner = CliRunner()


def _storyboard(scene_count: int = 2, shots_per_scene: int = 2) -> Storyboard:
    shots: list[StoryboardShot] = []
    elapsed = 0.0
    for scene_id in range(1, scene_count + 1):
        for order in range(1, shots_per_scene + 1):
            shots.append(
                StoryboardShot(
                    id=len(shots) + 1,
                    scene_id=scene_id,
                    order=order,
                    duration=3,
                    character="lin_tian",
                    action="draws a sword",
                    camera="medium shot",
                    speech_start=elapsed,
                    speech_end=elapsed + 3,
                    video_prompt=f"video prompt {len(shots) + 1}",
                    image_prompt=f"image prompt {len(shots) + 1}",
                    subtitle=f"line {len(shots) + 1}",
                )
            )
            elapsed += 3
    return Storyboard(
        title="Tu Tiên", style="cinematic", total_duration=elapsed, shots=tuple(shots)
    )


def _write_storyboard(path: Path, storyboard: Storyboard | None = None) -> Path:
    path.write_text(
        json.dumps((storyboard or _storyboard()).model_dump(), ensure_ascii=False), encoding="utf-8"
    )
    return path


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setattr(
        mock_module,
        "check_ffmpeg",
        lambda: CheckResult(name="FFmpeg", status=HealthStatus.OK, detail="7.0"),
    )


def _fake_runner(monkeypatch: pytest.MonkeyPatch, *, return_code: int = 0) -> list[list[str]]:
    commands: list[list[str]] = []

    def _run(command: list[str]) -> tuple[int, str]:
        commands.append(command)
        if return_code == 0:
            Path(command[-1]).write_bytes(b"fake mp4")
        return return_code, "" if return_code == 0 else "boom"

    monkeypatch.setattr(mock_module, "default_ffmpeg_runner", _run)
    return commands


# --- provider contract -----------------------------------------------------


def test_the_provider_accepts_references(tmp_path: Path) -> None:
    """The Sprint 025 contract is generate(request, references)."""
    provider: VideoProvider = MockVideoProvider(
        VideoProviderSettings(), VideoSettings(), tmp_path, runner=lambda _c: (0, "")
    )
    request = VideoGenerationRequest(scene_id=1, clip_id=1, duration=6.0)

    result = asyncio.run(provider.generate(request, ClipReferences()))

    assert result.clip_id == 1
    assert result.video_path == tmp_path / "shot_001.mp4"


def test_a_reference_still_is_preferred_over_the_requests_own(tmp_path: Path) -> None:
    offered = tmp_path / "scene.png"
    offered.write_bytes(b"png")
    own = tmp_path / "own.png"
    own.write_bytes(b"png")
    commands: list[list[str]] = []

    def _runner(command: list[str]) -> tuple[int, str]:
        commands.append(command)
        return 0, ""

    provider = MockVideoProvider(VideoProviderSettings(), VideoSettings(), tmp_path, runner=_runner)
    request = VideoGenerationRequest(scene_id=1, clip_id=1, reference_images=(own,))

    asyncio.run(provider.generate(request, ClipReferences(scene=offered)))

    assert str(offered) in commands[0]
    assert str(own) not in commands[0]


def test_generate_still_works_without_references(tmp_path: Path) -> None:
    provider = MockVideoProvider(
        VideoProviderSettings(), VideoSettings(), tmp_path, runner=lambda _c: (0, "")
    )

    result = asyncio.run(provider.generate(VideoGenerationRequest(scene_id=1, clip_id=2)))

    assert result.video_path == tmp_path / "shot_002.mp4"


def test_clip_files_are_named_per_the_specification() -> None:
    assert clip_filename(1) == "shot_001.mp4"
    assert clip_filename(42) == "shot_042.mp4"


# --- request building ------------------------------------------------------


def test_requests_carry_the_configured_frame_and_rate(tmp_path: Path) -> None:
    path = _write_storyboard(tmp_path / "storyboard.json")
    storyboard = read_storyboard(path)

    planned = build_requests(storyboard, VideoSettings())

    _clip, request = planned[0]
    assert (request.width, request.height) == (1080, 1920)  # portrait, per the project
    assert request.aspect_ratio == "9:16"
    assert request.fps == 30


def test_requests_record_the_shots_each_clip_covers(tmp_path: Path) -> None:
    storyboard = read_storyboard(_write_storyboard(tmp_path / "storyboard.json"))

    planned = build_requests(storyboard, VideoSettings())

    assert [request.shot_ids for _clip, request in planned] == [(1, 2), (3, 4)]
    assert [request.duration for _clip, request in planned] == [6.0, 6.0]


# --- CLI -------------------------------------------------------------------


def test_generate_renders_one_clip_per_planned_clip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    commands = _fake_runner(monkeypatch)
    path = _write_storyboard(tmp_path / "storyboard.json")

    result = runner.invoke(app, ["video", "generate", "--storyboard", str(path)])

    assert result.exit_code == 0
    clips = tmp_path / "out" / "video_clips"
    assert (clips / "shot_001.mp4").exists()
    assert (clips / "shot_002.mp4").exists()
    assert len(commands) == 2  # four 3s shots merged into two 6s clips


def test_the_clip_durations_land_in_the_required_band(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_runner(monkeypatch)
    path = _write_storyboard(tmp_path / "storyboard.json")

    runner.invoke(app, ["video", "generate", "--storyboard", str(path)])

    payload = json.loads(
        (tmp_path / "out" / "video_clips" / "manifest.json").read_text(encoding="utf-8")
    )
    assert all(4 <= clip["duration"] <= 8 for clip in payload["clips"])


def test_the_manifest_records_clip_identity_and_its_shots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_runner(monkeypatch)
    path = _write_storyboard(tmp_path / "storyboard.json")

    runner.invoke(app, ["video", "generate", "--storyboard", str(path)])

    payload = json.loads(
        (tmp_path / "out" / "video_clips" / "manifest.json").read_text(encoding="utf-8")
    )
    clip = payload["clips"][0]
    assert clip["clip_id"] == 1
    assert clip["shot_ids"] == [1, 2]
    assert clip["filename"] == "shot_001.mp4"
    assert clip["duration"] == 6.0


def test_a_scene_image_is_offered_as_a_reference(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    commands = _fake_runner(monkeypatch)
    path = _write_storyboard(tmp_path / "storyboard.json")
    images = tmp_path / "out" / "images"
    images.mkdir(parents=True)
    (images / "001.png").write_bytes(b"png")

    runner.invoke(app, ["video", "generate", "--storyboard", str(path)])

    # clip 1 belongs to scene 1, so it is conditioned on 001.png
    assert str(images / "001.png") in commands[0]


def test_generation_continues_past_a_failed_clip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_runner(monkeypatch, return_code=1)
    path = _write_storyboard(tmp_path / "storyboard.json")

    result = runner.invoke(app, ["video", "generate", "--storyboard", str(path)])

    assert result.exit_code == 1
    assert "0 clip(s), 2 failed" in result.stdout


def test_a_failed_clip_is_retried_before_giving_up(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    commands = _fake_runner(monkeypatch, return_code=1)
    path = _write_storyboard(tmp_path / "storyboard.json", _storyboard(1, 2))

    runner.invoke(app, ["video", "generate", "--storyboard", str(path)])

    assert len(commands) == 2  # one clip, attempted twice (retry_count=1)


# --- resume ----------------------------------------------------------------


def test_resume_skips_clips_already_rendered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_runner(monkeypatch)
    path = _write_storyboard(tmp_path / "storyboard.json")
    runner.invoke(app, ["video", "generate", "--storyboard", str(path)])

    commands = _fake_runner(monkeypatch)
    result = runner.invoke(app, ["video", "generate", "--storyboard", str(path), "--resume"])

    assert result.exit_code == 0
    assert commands == []  # nothing re-rendered, nothing re-spent


def test_resume_renders_only_what_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_runner(monkeypatch)
    path = _write_storyboard(tmp_path / "storyboard.json")
    runner.invoke(app, ["video", "generate", "--storyboard", str(path)])
    (tmp_path / "out" / "video_clips" / "shot_002.mp4").unlink()

    commands = _fake_runner(monkeypatch)
    runner.invoke(app, ["video", "generate", "--storyboard", str(path), "--resume"])

    assert len(commands) == 1
    assert commands[0][-1].endswith("shot_002.mp4")


def test_without_resume_everything_is_rendered_again(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_runner(monkeypatch)
    path = _write_storyboard(tmp_path / "storyboard.json")
    runner.invoke(app, ["video", "generate", "--storyboard", str(path)])

    commands = _fake_runner(monkeypatch)
    runner.invoke(app, ["video", "generate", "--storyboard", str(path)])

    assert len(commands) == 2


def test_a_reused_clip_is_still_reported_in_the_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_runner(monkeypatch)
    path = _write_storyboard(tmp_path / "storyboard.json")
    runner.invoke(app, ["video", "generate", "--storyboard", str(path)])

    _fake_runner(monkeypatch)
    runner.invoke(app, ["video", "generate", "--storyboard", str(path), "--resume"])

    payload = json.loads(
        (tmp_path / "out" / "video_clips" / "manifest.json").read_text(encoding="utf-8")
    )
    assert payload["count"] == 2
    assert all(clip["status"] == "completed" for clip in payload["clips"])


# --- guards ----------------------------------------------------------------


def test_a_missing_storyboard_fails_cleanly(tmp_path: Path) -> None:
    result = runner.invoke(app, ["video", "generate", "--storyboard", str(tmp_path / "no.json")])

    assert result.exit_code == 1
    assert "storyboard not found" in result.stdout


def test_an_invalid_storyboard_fails_cleanly(tmp_path: Path) -> None:
    bad = tmp_path / "storyboard.json"
    bad.write_text("{not json", encoding="utf-8")

    result = runner.invoke(app, ["video", "generate", "--storyboard", str(bad)])

    assert result.exit_code == 1
    assert "invalid JSON" in result.stdout


def test_an_empty_storyboard_is_rejected(tmp_path: Path) -> None:
    path = _write_storyboard(tmp_path / "storyboard.json", Storyboard(title="empty"))

    result = runner.invoke(app, ["video", "generate", "--storyboard", str(path)])

    assert result.exit_code == 1
    assert "no shots" in result.stdout


def test_a_dry_run_submits_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    commands = _fake_runner(monkeypatch)
    path = _write_storyboard(tmp_path / "storyboard.json")

    result = runner.invoke(app, ["video", "generate", "--storyboard", str(path), "--dry-run"])

    assert result.exit_code == 0
    assert commands == []
    assert not (tmp_path / "out" / "video_clips").exists()


def test_the_legacy_movie_path_still_works(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Sprint 021's scene-per-clip route must keep working."""
    _fake_runner(monkeypatch)
    movie = tmp_path / "movie.json"
    movie.write_text(
        json.dumps(
            {
                "title": "t",
                "duration": 30,
                "scenes": [
                    {"id": 1, "duration": 5, "video_prompt": "a"},
                    {"id": 2, "duration": 5, "video_prompt": "b"},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["video", "generate", "--movie", str(movie)])

    assert result.exit_code == 0


def test_clips_that_cannot_reach_the_minimum_are_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A 9s scene of 3s shots can only split 6+3; the 3s clip is flagged."""
    _fake_runner(monkeypatch)
    path = _write_storyboard(tmp_path / "storyboard.json", _storyboard(1, 3))

    result = runner.invoke(app, ["video", "generate", "--storyboard", str(path), "--dry-run"])

    assert "under 4s" in result.stdout
