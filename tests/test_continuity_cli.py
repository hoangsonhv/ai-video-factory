"""Tests for the ``ai-video-factory continuity`` CLI command (offline)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.domain.value_objects.continuity import (
    CharacterBible,
    PromptScoreDocument,
    VisualContextDocument,
    WorldBible,
)
from ai_video_factory.domain.value_objects.storyboard import Storyboard, StoryboardShot
from ai_video_factory.interface.cli.app import app

runner = CliRunner()


def _storyboard(shots: int = 4, scenes: int = 2) -> Storyboard:
    entries: list[StoryboardShot] = []
    elapsed = 0.0
    for scene_id in range(1, scenes + 1):
        for order in range(1, (shots // scenes) + 1):
            entries.append(
                StoryboardShot(
                    id=len(entries) + 1,
                    scene_id=scene_id,
                    order=order,
                    duration=3,
                    camera="medium shot",
                    character="lin_tian",
                    action=f"action {len(entries) + 1}",
                    expression="resolve",
                    environment="embers drifting",
                    lighting="hard key",
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


def _write_inputs(tmp_path: Path) -> Path:
    out = tmp_path / "out"
    _write(
        out / "character_library.json",
        {
            "characters": [
                {
                    "id": "lin_tian",
                    "master_prompt": "Lâm Thiên, long black hair",
                    "negative_prompt": "inconsistent face",
                    "appearance": {"hair": "long black hair", "eyes": "golden eyes"},
                    "outfit": {"clothes": "white silk robe", "accessories": "jade pendant"},
                }
            ]
        },
    )
    _write(
        out / "movie_consistent.json",
        {
            "title": "Tu Tiên",
            "genre": "cultivation",
            "style": "cinematic",
            "duration": 60,
            "locations": [{"id": "cliff", "name": "Cliff", "description": "sunrise over the sea"}],
            "characters": [{"id": "lin_tian", "name": "Lâm Thiên"}],
            "scenes": [{"id": 1, "duration": 6}],
        },
    )
    return _write(tmp_path / "storyboard.json", _storyboard().model_dump())


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))


# --- happy path ------------------------------------------------------------


def test_it_writes_every_documented_artifact(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)

    result = runner.invoke(app, ["continuity", "--storyboard", str(storyboard)])

    assert result.exit_code == 0
    out = tmp_path / "out"
    for name in (
        "character_bible.json",
        "world_bible.json",
        "visual_context.json",
        "shot_image_prompts.json",
        "prompt_scores.json",
    ):
        assert (out / name).exists(), name


def test_the_artifacts_are_schema_valid(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)
    runner.invoke(app, ["continuity", "--storyboard", str(storyboard)])
    out = tmp_path / "out"

    CharacterBible.model_validate(json.loads((out / "character_bible.json").read_text("utf-8")))
    WorldBible.model_validate(json.loads((out / "world_bible.json").read_text("utf-8")))
    context = VisualContextDocument.model_validate(
        json.loads((out / "visual_context.json").read_text("utf-8"))
    )

    assert len(context.shots) == 4


def test_the_scores_document_reports_the_run(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)
    runner.invoke(app, ["continuity", "--storyboard", str(storyboard)])

    payload = json.loads((tmp_path / "out" / "prompt_scores.json").read_text("utf-8"))
    PromptScoreDocument.model_validate({k: payload[k] for k in ("threshold", "scores")})

    assert payload["threshold"] == 90
    assert "average" in payload
    assert "failing" in payload


def test_one_prompt_is_written_per_shot(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)

    runner.invoke(app, ["continuity", "--storyboard", str(storyboard)])

    payload = json.loads((tmp_path / "out" / "shot_image_prompts.json").read_text("utf-8"))
    assert len(payload["image_prompts"]) == 4
    assert payload["image_prompts"][0]["prompt"]


def test_every_prompt_carries_the_bibles_and_its_neighbours(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)

    runner.invoke(app, ["continuity", "--storyboard", str(storyboard)])

    prompt = json.loads((tmp_path / "out" / "shot_image_prompts.json").read_text("utf-8"))[
        "image_prompts"
    ][1]["prompt"]

    for section in ("Character", "Action", "Environment", "Camera", "Negative Prompt"):
        assert f"{section}:" in prompt, section
    assert "Lâm Thiên" in prompt  # UTF-8 survives the round trip


def test_it_leaves_the_existing_image_prompts_untouched(tmp_path: Path) -> None:
    """image_prompts.json belongs to the `image` stage; this writes its own file."""
    storyboard = _write_inputs(tmp_path)
    existing = _write(tmp_path / "out" / "image_prompts.json", {"image_prompts": [{"prompt": "x"}]})
    before = existing.read_text(encoding="utf-8")

    runner.invoke(app, ["continuity", "--storyboard", str(storyboard)])

    assert existing.read_text(encoding="utf-8") == before


# --- bibles ----------------------------------------------------------------


def test_derived_bibles_are_reported(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)

    result = runner.invoke(app, ["continuity", "--storyboard", str(storyboard)])

    assert "derived the bibles" in result.stdout


def test_a_hand_edited_bible_survives_a_rerun(tmp_path: Path) -> None:
    """Editing the bible is the intended way to enrich art direction."""
    storyboard = _write_inputs(tmp_path)
    runner.invoke(app, ["continuity", "--storyboard", str(storyboard)])

    world_path = tmp_path / "out" / "world_bible.json"
    world = json.loads(world_path.read_text("utf-8"))
    world["era"] = "Song dynasty, 12th century"
    world_path.write_text(json.dumps(world, ensure_ascii=False), encoding="utf-8")

    result = runner.invoke(app, ["continuity", "--storyboard", str(storyboard)])

    assert result.exit_code == 0
    assert json.loads(world_path.read_text("utf-8"))["era"] == "Song dynasty, 12th century"
    prompt = json.loads((tmp_path / "out" / "shot_image_prompts.json").read_text("utf-8"))[
        "image_prompts"
    ][0]["prompt"]
    assert "Song dynasty" in prompt


def test_a_rerun_with_both_bibles_present_does_not_rederive(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)
    runner.invoke(app, ["continuity", "--storyboard", str(storyboard)])

    result = runner.invoke(app, ["continuity", "--storyboard", str(storyboard)])

    assert "derived the bibles" not in result.stdout


# --- threshold and reporting ----------------------------------------------


def test_an_unreachable_threshold_is_reported_not_looped(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)

    result = runner.invoke(
        app, ["continuity", "--storyboard", str(storyboard), "--threshold", "100"]
    )

    assert result.exit_code == 0
    assert "stayed below 100" in result.stdout


def test_the_average_score_is_reported(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)

    result = runner.invoke(app, ["continuity", "--storyboard", str(storyboard)])

    assert "average score" in result.stdout


# --- failures --------------------------------------------------------------


def test_a_missing_storyboard_fails_cleanly(tmp_path: Path) -> None:
    result = runner.invoke(app, ["continuity", "--storyboard", str(tmp_path / "no.json")])

    assert result.exit_code == 1
    assert "storyboard not found" in result.stdout


def test_a_missing_character_library_fails_cleanly(tmp_path: Path) -> None:
    storyboard = _write(tmp_path / "storyboard.json", _storyboard().model_dump())

    result = runner.invoke(app, ["continuity", "--storyboard", str(storyboard)])

    assert result.exit_code == 1
    assert "character library not found" in result.stdout


def test_an_invalid_storyboard_fails_cleanly(tmp_path: Path) -> None:
    bad = tmp_path / "storyboard.json"
    bad.write_text("{not json", encoding="utf-8")

    result = runner.invoke(app, ["continuity", "--storyboard", str(bad)])

    assert result.exit_code == 1
    assert "invalid JSON" in result.stdout


def test_a_storyboard_without_shots_is_rejected_with_guidance(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    empty = _write(tmp_path / "empty.json", Storyboard(title="t").model_dump())

    result = runner.invoke(app, ["continuity", "--storyboard", str(empty)])

    assert result.exit_code == 1
    assert "run `storyboard`" in result.stdout


def test_the_existing_commands_still_register() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("continuity", "storyboard", "director", "video", "compose", "image"):
        assert command in result.stdout
