"""Tests for the ``ai-video-factory character`` CLI commands (no real API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.domain.value_objects.character_library import CharacterLibrary
from ai_video_factory.domain.value_objects.movie import (
    Appearance,
    Camera,
    Character,
    Location,
    Movie,
    Scene,
)
from ai_video_factory.interface.cli.app import app

runner = CliRunner()

_ORIGINAL_IMAGE_PROMPT = "standing on a cliff at sunrise"


def _movie() -> Movie:
    return Movie(
        title="Tu Tiên",
        genre="cultivation",
        style="cinematic",
        duration=60,
        characters=(
            Character(
                id="lin_tian",
                name="Lâm Thiên",
                gender="male",
                age=18,
                appearance=Appearance(hair="long black hair", clothes="white silk robe"),
                voice="young male, calm",
            ),
            # a duplicate record of the same character — must be merged away
            Character(
                id="lin_tian",
                name="Lâm Thiên",
                appearance=Appearance(hair="white hair", eyes="golden eyes"),
            ),
            Character(id="ma_nu", name="Ma Nữ", appearance=Appearance(hair="white hair")),
        ),
        locations=(Location(id="cliff", name="Cliff", description="sunrise"),),
        scenes=(
            Scene(
                id=1,
                duration=5,
                location="cliff",
                characters=("lin_tian",),
                camera=Camera(shot="wide", movement="drone", lens="35mm"),
                action="draws a sword",
                dialogue="Có ai không?",
                image_prompt=_ORIGINAL_IMAGE_PROMPT,
                video_prompt="camera pushes in slowly",
            ),
        ),
    )


def _write_movie(path: Path) -> Path:
    path.write_text(json.dumps(_movie().model_dump(), ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))


# --- character build -------------------------------------------------------


def test_build_writes_a_schema_valid_library(tmp_path: Path) -> None:
    movie_path = _write_movie(tmp_path / "movie.json")

    result = runner.invoke(app, ["character", "build", "--input", str(movie_path)])

    assert result.exit_code == 0
    library_path = tmp_path / "out" / "character_library.json"
    assert library_path.exists()
    data = json.loads(library_path.read_text(encoding="utf-8"))
    library = CharacterLibrary.model_validate(data)  # JSON schema validation

    assert [profile.id for profile in library.characters] == ["lin_tian", "ma_nu"]
    profile = library.characters[0]
    assert profile.seed > 0
    assert "Lâm Thiên" in profile.master_prompt  # Vietnamese UTF-8 preserved
    assert profile.appearance.hair == "long black hair"  # first record won the merge
    assert profile.outfit.clothes == "white silk robe"
    assert "inconsistent face" in profile.negative_prompt


def test_build_reports_merged_duplicates(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["character", "build", "--input", str(_write_movie(tmp_path / "movie.json"))]
    )

    assert result.exit_code == 0
    assert "Merged 1 duplicate" in result.stdout


def test_build_missing_movie_fails(tmp_path: Path) -> None:
    result = runner.invoke(app, ["character", "build", "--input", str(tmp_path / "nope.json")])
    assert result.exit_code == 1


def test_build_invalid_movie_fails(tmp_path: Path) -> None:
    bad = tmp_path / "movie.json"
    bad.write_text("{not json", encoding="utf-8")

    assert runner.invoke(app, ["character", "build", "--input", str(bad)]).exit_code == 1


# --- character inject ------------------------------------------------------


def _build_then_inject(tmp_path: Path) -> Path:
    movie_path = _write_movie(tmp_path / "movie.json")
    runner.invoke(app, ["character", "build", "--input", str(movie_path)])
    result = runner.invoke(app, ["character", "inject", "--movie", str(movie_path)])
    assert result.exit_code == 0
    return tmp_path / "out" / "movie_consistent.json"


def test_inject_writes_a_consistent_movie(tmp_path: Path) -> None:
    output_path = _build_then_inject(tmp_path)

    assert output_path.exists()
    data = json.loads(output_path.read_text(encoding="utf-8"))
    injected = Movie.model_validate(data)  # still a valid Movie
    prompt = injected.scenes[0].image_prompt

    assert prompt.startswith("Lâm Thiên")  # master prompt prepended
    assert _ORIGINAL_IMAGE_PROMPT in prompt  # original preserved
    assert "negative: inconsistent face" in prompt  # negative appended
    assert "camera pushes in slowly" in injected.scenes[0].video_prompt


def test_inject_leaves_the_source_movie_untouched(tmp_path: Path) -> None:
    _build_then_inject(tmp_path)
    source = json.loads((tmp_path / "movie.json").read_text(encoding="utf-8"))

    assert source["scenes"][0]["image_prompt"] == _ORIGINAL_IMAGE_PROMPT


def test_inject_without_a_library_fails(tmp_path: Path) -> None:
    movie_path = _write_movie(tmp_path / "movie.json")

    result = runner.invoke(app, ["character", "inject", "--movie", str(movie_path)])

    assert result.exit_code == 1
    assert not (tmp_path / "out" / "movie_consistent.json").exists()


def test_inject_accepts_an_explicit_library_path(tmp_path: Path) -> None:
    movie_path = _write_movie(tmp_path / "movie.json")
    runner.invoke(app, ["character", "build", "--input", str(movie_path)])
    library = tmp_path / "out" / "character_library.json"
    elsewhere = tmp_path / "custom_library.json"
    elsewhere.write_text(library.read_text(encoding="utf-8"), encoding="utf-8")
    library.unlink()

    result = runner.invoke(
        app,
        ["character", "inject", "--movie", str(movie_path), "--library", str(elsewhere)],
    )

    assert result.exit_code == 0
    assert (tmp_path / "out" / "movie_consistent.json").exists()


def test_character_commands_touch_no_other_output(tmp_path: Path) -> None:
    _build_then_inject(tmp_path)
    out = tmp_path / "out"

    assert sorted(p.name for p in out.iterdir()) == [
        "character_library.json",
        "movie_consistent.json",
    ]
