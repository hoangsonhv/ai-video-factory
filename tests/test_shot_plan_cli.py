"""Tests for the ``ai-video-factory shot-plan`` CLI command (offline)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.domain.value_objects.shot_plan import (
    CLOSE_SHOTS,
    ShotPlan,
    ShotStatistics,
    ShotType,
)
from ai_video_factory.domain.value_objects.storyboard import Storyboard, StoryboardShot
from ai_video_factory.interface.cli.app import app

runner = CliRunner()


def _storyboard(scenes: int = 4, per_scene: int = 3) -> Storyboard:
    entries: list[StoryboardShot] = []
    elapsed = 0.0
    for scene_id in range(1, scenes + 1):
        for order in range(1, per_scene + 1):
            entries.append(
                StoryboardShot(
                    id=len(entries) + 1,
                    scene_id=scene_id,
                    order=order,
                    duration=3,
                    camera="close-up",
                    camera_motion="static",
                    character="lin_tian",
                    action=f"ride through the district {len(entries) + 1}",
                    expression="resolve",
                    environment="neon signs blurring past",
                    lighting="cool blue neon",
                    subtitle=f"line {len(entries) + 1}",
                    speech_start=elapsed,
                    speech_end=elapsed + 3,
                )
            )
            elapsed += 3
    return Storyboard(
        title="Tu Tiên", style="cinematic", total_duration=elapsed, shots=tuple(entries)
    )


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_inputs(tmp_path: Path, *, with_movie: bool = True) -> Path:
    out = tmp_path / "out"
    _write(
        out / "character_bible.json",
        {
            "characters": [
                {
                    "id": "lin_tian",
                    "name": "Lâm Thiên",
                    "appearance": "long black hair",
                    "wardrobe": "white silk robe",
                    "negative_prompt": "inconsistent face",
                }
            ]
        },
    )
    _write(
        out / "world_bible.json",
        {
            "title": "Tu Tiên",
            "genre": "cultivation",
            "style": "cinematic",
            "art_direction": "cinematic",
            "negative_prompt": "blurry",
            "locations": [
                {
                    "id": "city",
                    "name": "City",
                    "description": "A neon metropolis at night",
                    "weather": "light rain",
                }
            ],
        },
    )
    if with_movie:
        _write(
            out / "movie_directed.json",
            {
                "title": "Tu Tiên",
                "duration": 60,
                "scenes": [
                    {
                        "id": scene_id,
                        "duration": 9,
                        "location": "city",
                        "characters": ["lin_tian"],
                        "action": "ride through traffic",
                        "emotion": "determined",
                    }
                    for scene_id in range(1, 5)
                ],
            },
        )
    return _write(tmp_path / "storyboard.json", _storyboard().model_dump())


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))


# --- happy path ------------------------------------------------------------


def test_it_writes_the_plan_the_statistics_and_the_prompts(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)

    result = runner.invoke(app, ["shot-plan", "--storyboard", str(storyboard)])

    assert result.exit_code == 0, result.output
    out = tmp_path / "out"
    for name in ("shot_plan.json", "shot_statistics.json", "shot_image_prompts.json"):
        assert (out / name).exists(), name


def test_the_artifacts_are_schema_valid(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)
    runner.invoke(app, ["shot-plan", "--storyboard", str(storyboard)])
    out = tmp_path / "out"

    plan = ShotPlan.model_validate(json.loads((out / "shot_plan.json").read_text("utf-8")))
    statistics = ShotStatistics.model_validate(
        json.loads((out / "shot_statistics.json").read_text("utf-8"))
    )

    assert len(plan.shots) == 12
    assert statistics.total == 12


def test_one_prompt_is_written_per_shot(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)
    runner.invoke(app, ["shot-plan", "--storyboard", str(storyboard)])

    payload = json.loads((tmp_path / "out" / "shot_image_prompts.json").read_text("utf-8"))

    assert len(payload["image_prompts"]) == 12


def test_the_statistics_hold_all_four_histograms(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)
    runner.invoke(app, ["shot-plan", "--storyboard", str(storyboard)])

    payload = json.loads((tmp_path / "out" / "shot_statistics.json").read_text("utf-8"))

    for key in ("shot_types", "lenses", "cameras", "body_visibility"):
        assert payload[key], key


# --- what the command is for ----------------------------------------------


def test_the_planned_film_is_not_mostly_portraits(tmp_path: Path) -> None:
    """The storyboard asks for a close-up on every shot; the plan overrules it."""
    storyboard = _write_inputs(tmp_path)
    runner.invoke(app, ["shot-plan", "--storyboard", str(storyboard)])

    plan = ShotPlan.model_validate(
        json.loads((tmp_path / "out" / "shot_plan.json").read_text("utf-8"))
    )
    close = sum(1 for shot in plan.shots if shot.shot_type in CLOSE_SHOTS)

    assert close <= len(plan.shots) * 0.2


def test_the_coverage_it_reports_is_inside_its_bounds(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)
    result = runner.invoke(app, ["shot-plan", "--storyboard", str(storyboard)])

    plan = ShotPlan.model_validate(
        json.loads((tmp_path / "out" / "shot_plan.json").read_text("utf-8"))
    )

    assert plan.distribution.valid, plan.distribution.issues
    assert "Coverage still outside" not in result.output


def test_every_planned_frame_states_an_environment(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)
    runner.invoke(app, ["shot-plan", "--storyboard", str(storyboard)])

    plan = ShotPlan.model_validate(
        json.loads((tmp_path / "out" / "shot_plan.json").read_text("utf-8"))
    )

    assert all(not shot.environment_visibility.is_empty for shot in plan.shots)


def test_no_prompt_carries_close_up_language_the_plan_refused(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)
    runner.invoke(app, ["shot-plan", "--storyboard", str(storyboard)])

    plan = ShotPlan.model_validate(
        json.loads((tmp_path / "out" / "shot_plan.json").read_text("utf-8"))
    )
    payload = json.loads((tmp_path / "out" / "shot_image_prompts.json").read_text("utf-8"))

    for shot, prompt in zip(plan.shots, payload["image_prompts"], strict=True):
        if shot.shot_type not in CLOSE_SHOTS and shot.shot_type is not ShotType.MEDIUM_CLOSE:
            positive = prompt["prompt"].split("Negative Prompt:")[0].lower()
            assert "close-up" not in positive
            assert "headshot" not in positive


# --- honest reporting ------------------------------------------------------


def test_it_says_when_no_directed_movie_was_found(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path, with_movie=False)

    result = runner.invoke(app, ["shot-plan", "--storyboard", str(storyboard)])

    assert result.exit_code == 0
    assert "no directed movie" in result.output


def test_it_warns_that_it_replaces_the_prompts_file(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)

    result = runner.invoke(app, ["shot-plan", "--storyboard", str(storyboard)])

    assert "character memory" in result.output


# --- failures --------------------------------------------------------------


def test_a_missing_storyboard_fails_loudly(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    result = runner.invoke(app, ["shot-plan", "--storyboard", str(tmp_path / "nope.json")])

    assert result.exit_code == 1
    assert "not found" in result.output


def test_a_missing_bible_fails_loudly(tmp_path: Path) -> None:
    storyboard = _write(tmp_path / "storyboard.json", _storyboard().model_dump())

    result = runner.invoke(app, ["shot-plan", "--storyboard", str(storyboard)])

    assert result.exit_code == 1
    assert "not found" in result.output


def test_a_custom_prompts_path_is_honoured(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)
    target = tmp_path / "elsewhere" / "prompts.json"

    result = runner.invoke(
        app, ["shot-plan", "--storyboard", str(storyboard), "--prompts", str(target)]
    )

    assert result.exit_code == 0
    assert target.exists()
    assert not (tmp_path / "out" / "shot_image_prompts.json").exists()
