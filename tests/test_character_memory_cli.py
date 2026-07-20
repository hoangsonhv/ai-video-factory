"""Tests for the ``ai-video-factory character memory`` CLI command (offline)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.domain.value_objects.character_memory import (
    AppearanceScoreDocument,
    CharacterMemoryDocument,
)
from ai_video_factory.domain.value_objects.storyboard import Storyboard, StoryboardShot
from ai_video_factory.interface.cli.app import app

runner = CliRunner()


def _storyboard(*characters: str) -> Storyboard:
    names = characters or ("lin_tian", "ma_nu", "lin_tian")
    return Storyboard(
        title="Tu Tiên",
        shots=tuple(
            StoryboardShot(
                id=index,
                scene_id=index,
                order=1,
                duration=3,
                character=name,
                action=f"action {index}",
            )
            for index, name in enumerate(names, start=1)
        ),
    )


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_inputs(tmp_path: Path) -> Path:
    out = tmp_path / "out"
    _write(
        out / "character_bible.json",
        {
            "characters": [
                {
                    "id": "lin_tian",
                    "name": "Lâm Thiên",
                    "appearance": "long black hair, golden eyes",
                    "wardrobe": "white silk robe",
                    "signature_props": "celestial sword",
                    "palette": "white and gold",
                },
                {"id": "ma_nu", "name": "Ma Nữ", "appearance": "white hair", "wardrobe": "cloak"},
            ]
        },
    )
    _write(
        out / "movie_consistent.json",
        {
            "title": "Tu Tiên",
            "style": "cinematic",
            "duration": 60,
            "characters": [
                {"id": "lin_tian", "name": "Lâm Thiên", "gender": "male", "age": 22},
                {"id": "ma_nu", "name": "Ma Nữ", "gender": "female", "age": 19},
            ],
            "scenes": [{"id": 1, "duration": 6}],
        },
    )
    _write(
        out / "shot_image_prompts.json",
        {
            "image_prompts": [
                {
                    "scene_number": index,
                    "prompt": f"continuity prompt {index}",
                    "aspect_ratio": "9:16",
                    "style": "cinematic",
                }
                for index in (1, 2, 3)
            ]
        },
    )
    return _write(tmp_path / "storyboard.json", _storyboard().model_dump())


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))


# --- happy path ------------------------------------------------------------


def test_it_writes_the_memory_and_the_scores(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)

    result = runner.invoke(app, ["character", "memory", "--storyboard", str(storyboard)])

    assert result.exit_code == 0
    out = tmp_path / "out"
    CharacterMemoryDocument.model_validate(
        json.loads((out / "character_memory.json").read_text("utf-8"))
    )
    payload = json.loads((out / "appearance_scores.json").read_text("utf-8"))
    AppearanceScoreDocument.model_validate({k: payload[k] for k in ("threshold", "scores")})


def test_the_memory_holds_every_documented_field(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)

    runner.invoke(app, ["character", "memory", "--storyboard", str(storyboard)])

    entry = json.loads((tmp_path / "out" / "character_memory.json").read_text("utf-8"))[
        "characters"
    ][0]
    for field in (
        "character_id",
        "canonical_face",
        "canonical_hair",
        "canonical_body",
        "canonical_clothes",
        "canonical_weapon",
        "canonical_expression",
        "canonical_color_palette",
        "reference_image",
        "appearance_hash",
    ):
        assert field in entry, field


def test_the_prompts_are_rewritten_with_the_remembered_identity(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)

    runner.invoke(app, ["character", "memory", "--storyboard", str(storyboard)])

    prompts = json.loads((tmp_path / "out" / "shot_image_prompts.json").read_text("utf-8"))[
        "image_prompts"
    ]
    assert "Reference Image:" in prompts[0]["prompt"]
    assert "Appearance Summary:" in prompts[0]["prompt"]
    assert "Previous Generated Appearance:" in prompts[0]["prompt"]
    assert "continuity prompt 1" in prompts[0]["prompt"]  # the base prompt survives


def test_the_scores_are_reported_per_shot(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)

    result = runner.invoke(app, ["character", "memory", "--storyboard", str(storyboard)])

    payload = json.loads((tmp_path / "out" / "appearance_scores.json").read_text("utf-8"))
    assert len(payload["scores"]) == 3
    assert "average" in payload
    assert "average appearance score" in result.stdout


# --- reference adoption ----------------------------------------------------


def test_a_generated_image_is_adopted_as_the_reference(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)
    images = tmp_path / "out" / "images"
    images.mkdir(parents=True, exist_ok=True)
    (images / "001.png").write_bytes(b"png")

    runner.invoke(app, ["character", "memory", "--storyboard", str(storyboard)])

    memory = json.loads((tmp_path / "out" / "character_memory.json").read_text("utf-8"))
    lin_tian = next(c for c in memory["characters"] if c["character_id"] == "lin_tian")
    assert lin_tian["reference_image"].endswith("001.png")


def test_characters_without_an_image_are_reported(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)

    result = runner.invoke(app, ["character", "memory", "--storyboard", str(storyboard)])

    assert "no reference image yet" in result.stdout


def test_an_adopted_reference_survives_a_rerun(tmp_path: Path) -> None:
    """Re-pointing it at a later image would redefine the character."""
    storyboard = _write_inputs(tmp_path)
    images = tmp_path / "out" / "images"
    images.mkdir(parents=True, exist_ok=True)
    (images / "001.png").write_bytes(b"png")
    runner.invoke(app, ["character", "memory", "--storyboard", str(storyboard)])

    (images / "003.png").write_bytes(b"png")
    runner.invoke(app, ["character", "memory", "--storyboard", str(storyboard)])

    memory = json.loads((tmp_path / "out" / "character_memory.json").read_text("utf-8"))
    lin_tian = next(c for c in memory["characters"] if c["character_id"] == "lin_tian")
    assert lin_tian["reference_image"].endswith("001.png")


def test_the_provider_reference_capability_is_reported(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)

    result = runner.invoke(app, ["character", "memory", "--storyboard", str(storyboard)])

    assert "takes no reference image" in result.stdout


# --- memory across runs ----------------------------------------------------


def test_a_hand_edited_canon_survives_a_rerun(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)
    runner.invoke(app, ["character", "memory", "--storyboard", str(storyboard)])

    memory_path = tmp_path / "out" / "character_memory.json"
    memory = json.loads(memory_path.read_text("utf-8"))
    memory["characters"][0]["canonical_hair"] = "silver hair"
    memory_path.write_text(json.dumps(memory, ensure_ascii=False), encoding="utf-8")

    runner.invoke(app, ["character", "memory", "--storyboard", str(storyboard)])

    assert json.loads(memory_path.read_text("utf-8"))["characters"][0]["canonical_hair"] == (
        "silver hair"
    )


def test_a_hand_edited_canon_reaches_the_prompt(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)
    runner.invoke(app, ["character", "memory", "--storyboard", str(storyboard)])
    memory_path = tmp_path / "out" / "character_memory.json"
    memory = json.loads(memory_path.read_text("utf-8"))
    memory["characters"][0]["canonical_clothes"] = "obsidian battle robe"
    memory_path.write_text(json.dumps(memory, ensure_ascii=False), encoding="utf-8")

    _write_inputs(tmp_path)  # reset the prompts to their un-enriched form
    runner.invoke(app, ["character", "memory", "--storyboard", str(storyboard)])

    prompts = json.loads((tmp_path / "out" / "shot_image_prompts.json").read_text("utf-8"))
    assert "obsidian battle robe" in prompts["image_prompts"][0]["prompt"]


def test_a_tampered_appearance_hash_is_flagged_as_drift(tmp_path: Path) -> None:
    storyboard = _write_inputs(tmp_path)
    runner.invoke(app, ["character", "memory", "--storyboard", str(storyboard)])
    memory_path = tmp_path / "out" / "character_memory.json"
    memory = json.loads(memory_path.read_text("utf-8"))
    memory["characters"][0]["canonical_hair"] = "changed without rehashing"
    memory_path.write_text(json.dumps(memory, ensure_ascii=False), encoding="utf-8")

    result = runner.invoke(app, ["character", "memory", "--storyboard", str(storyboard)])

    assert "no longer" in result.stdout


# --- failures --------------------------------------------------------------


def test_a_missing_storyboard_fails_cleanly(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    result = runner.invoke(app, ["character", "memory", "--storyboard", str(tmp_path / "no.json")])

    assert result.exit_code == 1
    assert "storyboard not found" in result.stdout


def test_missing_prompts_point_at_the_continuity_stage(tmp_path: Path) -> None:
    storyboard = _write(tmp_path / "storyboard.json", _storyboard().model_dump())

    result = runner.invoke(app, ["character", "memory", "--storyboard", str(storyboard)])

    assert result.exit_code == 1
    assert "run `continuity`" in result.stdout


def test_a_missing_character_bible_fails_cleanly(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    (tmp_path / "out" / "character_bible.json").unlink()
    storyboard = tmp_path / "storyboard.json"

    result = runner.invoke(app, ["character", "memory", "--storyboard", str(storyboard)])

    assert result.exit_code == 1
    assert "character bible not found" in result.stdout


def test_the_existing_character_commands_still_register() -> None:
    result = runner.invoke(app, ["character", "--help"])

    assert result.exit_code == 0
    for command in ("build", "inject", "memory"):
        assert command in result.stdout
