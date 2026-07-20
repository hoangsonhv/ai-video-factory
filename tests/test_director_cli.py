"""Tests for the ``ai-video-factory director`` CLI command (no real API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.domain.value_objects.character_library import CharacterLibrary
from ai_video_factory.domain.value_objects.director import DirectedMovie
from ai_video_factory.domain.value_objects.movie import Camera, Location, Movie, Scene
from ai_video_factory.infrastructure.director.report import DirectionReport
from ai_video_factory.interface.cli import director_commands as dc
from ai_video_factory.interface.cli.app import app

runner = CliRunner()

_PLAN = {
    "scenes": [
        {
            "scene_id": 1,
            "shots": [
                {
                    "id": 1,
                    "duration": 3,
                    "camera": "medium shot",
                    "camera_motion": "slow push in",
                    "lens": "50mm",
                    "framing": "centred",
                    "subject": "lin_tian",
                    "action": "draws a sword",
                    "expression": "resolve hardening",
                    "environment_motion": "embers drifting",
                    "lighting": "hard key",
                    "transition": "cut",
                    "video_prompt": "he draws the blade",
                }
            ],
        }
    ]
}


def _movie() -> Movie:
    return Movie(
        title="Tu Tiên",
        genre="cultivation",
        style="cinematic",
        duration=60,
        locations=(Location(id="cliff", name="Cliff", description="sunrise"),),
        scenes=(
            Scene(
                id=1,
                duration=5,
                location="cliff",
                characters=("lin_tian",),
                camera=Camera(shot="wide shot", movement="drone", lens="35mm"),
                action="walks",
                emotion="resolve",
                dialogue="Có ai không?",
                image_prompt="an image prompt",
                video_prompt="a video prompt",
            ),
        ),
    )


def _library() -> CharacterLibrary:
    return CharacterLibrary.model_validate(
        {
            "characters": [
                {
                    "id": "lin_tian",
                    "master_prompt": "Lâm Thiên, long black hair",
                    "negative_prompt": "inconsistent face",
                    "seed": 1234,
                }
            ]
        }
    )


class _FakeService:
    """Stands in for the LLM-backed director; applies a scripted plan."""

    def __init__(self, real: object) -> None:
        self._real = real

    async def direct(
        self,
        movie: Movie,
        library: CharacterLibrary | None = None,
        *,
        resume_from: DirectedMovie | None = None,
    ) -> tuple[DirectedMovie, DirectionReport]:
        from ai_video_factory.infrastructure.director.shot_parser import parse_shot_plan

        plan = parse_shot_plan(json.dumps(_PLAN), {s.id: s.duration for s in movie.scenes})
        directed = self._real.apply(movie, plan, library)  # type: ignore[attr-defined]
        return directed, DirectionReport(directed=len(movie.scenes))


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))


@pytest.fixture
def _fake_director(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the provider-backed factory with a scripted service."""
    from ai_video_factory.infrastructure.director.service import DirectorService
    from ai_video_factory.infrastructure.prompts.service import PromptService

    def _from_settings(
        settings: object,
        *,
        on_progress: object = None,
        on_scene_saved: object = None,
    ) -> _FakeService:
        return _FakeService(DirectorService(None, PromptService.create(Path("prompts"))))  # type: ignore[arg-type]

    monkeypatch.setattr(dc.DirectorService, "from_settings", staticmethod(_from_settings))


def _write_movie(path: Path, movie: Movie | None = None) -> Path:
    path.write_text(
        json.dumps((movie or _movie()).model_dump(), ensure_ascii=False), encoding="utf-8"
    )
    return path


def _write_library(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_library().model_dump(), ensure_ascii=False), encoding="utf-8")
    return path


# --- happy path ------------------------------------------------------------


def test_director_writes_a_schema_valid_directed_movie(
    tmp_path: Path, _fake_director: None
) -> None:
    movie = _write_movie(tmp_path / "movie_consistent.json")
    _write_library(tmp_path / "out" / "character_library.json")

    result = runner.invoke(app, ["director", "--movie", str(movie)])

    assert result.exit_code == 0
    directed_path = tmp_path / "out" / "movie_directed.json"
    data = json.loads(directed_path.read_text(encoding="utf-8"))
    directed = DirectedMovie.model_validate(data)  # JSON schema validation

    assert len(directed.scenes) == 1
    scene = data["scenes"][0]
    assert scene["shots"][0]["camera"] == "medium shot"
    assert scene["shots"][0]["environment_motion"] == "embers drifting"
    assert "Lâm Thiên" in scene["shots"][0]["video_prompt"]  # library combined in
    assert "temporally coherent" in scene["shots"][0]["video_prompt"]  # targets video


def test_the_directed_output_is_still_a_valid_movie(tmp_path: Path, _fake_director: None) -> None:
    movie = _write_movie(tmp_path / "movie_consistent.json")
    _write_library(tmp_path / "out" / "character_library.json")

    runner.invoke(app, ["director", "--movie", str(movie)])

    data = json.loads((tmp_path / "out" / "movie_directed.json").read_text(encoding="utf-8"))
    restored = Movie.model_validate(data)  # every existing stage can still read it

    assert restored.scenes[0].video_prompt == "a video prompt"
    assert restored.scenes[0].dialogue == "Có ai không?"  # Vietnamese preserved


def test_director_leaves_the_source_movie_untouched(tmp_path: Path, _fake_director: None) -> None:
    movie = _write_movie(tmp_path / "movie_consistent.json")
    _write_library(tmp_path / "out" / "character_library.json")

    runner.invoke(app, ["director", "--movie", str(movie)])

    source = json.loads(movie.read_text(encoding="utf-8"))
    assert "shots" not in source["scenes"][0]
    assert source["scenes"][0]["video_prompt"] == "a video prompt"


def test_director_works_without_a_character_library(tmp_path: Path, _fake_director: None) -> None:
    movie = _write_movie(tmp_path / "movie_consistent.json")

    result = runner.invoke(app, ["director", "--movie", str(movie)])

    assert result.exit_code == 0
    assert "no character library" in result.stdout
    assert (tmp_path / "out" / "movie_directed.json").exists()


def test_an_explicit_library_path_is_honoured(tmp_path: Path, _fake_director: None) -> None:
    movie = _write_movie(tmp_path / "movie_consistent.json")
    elsewhere = _write_library(tmp_path / "custom_library.json")

    result = runner.invoke(app, ["director", "--movie", str(movie), "--library", str(elsewhere)])

    assert result.exit_code == 0
    data = json.loads((tmp_path / "out" / "movie_directed.json").read_text(encoding="utf-8"))
    assert "Lâm Thiên" in data["scenes"][0]["shots"][0]["video_prompt"]


def test_director_touches_no_other_output(tmp_path: Path, _fake_director: None) -> None:
    movie = _write_movie(tmp_path / "movie_consistent.json")
    _write_library(tmp_path / "out" / "character_library.json")

    runner.invoke(app, ["director", "--movie", str(movie)])

    out = tmp_path / "out"
    assert sorted(p.name for p in out.iterdir()) == [
        "character_library.json",
        "movie_directed.json",
    ]


# --- failure handling ------------------------------------------------------


def test_a_missing_movie_fails_cleanly(tmp_path: Path) -> None:
    result = runner.invoke(app, ["director", "--movie", str(tmp_path / "nope.json")])

    assert result.exit_code == 1
    assert "movie file not found" in result.stdout


def test_an_invalid_movie_fails_cleanly(tmp_path: Path) -> None:
    bad = tmp_path / "movie.json"
    bad.write_text("{not json", encoding="utf-8")

    result = runner.invoke(app, ["director", "--movie", str(bad)])

    assert result.exit_code == 1
    assert "invalid JSON" in result.stdout


def test_a_malformed_library_fails_cleanly(tmp_path: Path, _fake_director: None) -> None:
    movie = _write_movie(tmp_path / "movie_consistent.json")
    library = tmp_path / "out" / "character_library.json"
    library.parent.mkdir(parents=True, exist_ok=True)
    library.write_text("{not json", encoding="utf-8")

    result = runner.invoke(app, ["director", "--movie", str(movie)])

    assert result.exit_code == 1
    assert not (tmp_path / "out" / "movie_directed.json").exists()


def test_the_existing_commands_still_register() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("movie", "character", "director", "image", "tts", "compose", "video"):
        assert command in result.stdout
