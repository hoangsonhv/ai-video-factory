"""Tests for the ``ai-video-factory movie`` CLI command (no real API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.domain.value_objects.chapter import StoryChapter
from ai_video_factory.domain.value_objects.movie import (
    Appearance,
    Camera,
    Character,
    Location,
    Movie,
    Scene,
)
from ai_video_factory.interface.cli import movie_commands as mc
from ai_video_factory.interface.cli.app import app

runner = CliRunner()


def _movie() -> Movie:
    return Movie(
        title="The Midnight Delivery",
        genre="horror",
        style="cinematic",
        duration=60,
        characters=(
            Character(id="shipper", name="Nam", appearance=Appearance(hair="black")),
            Character(id="ghost", name="Ma", appearance=Appearance(hair="white")),
        ),
        locations=(Location(id="cemetery", name="Cemetery", description="foggy"),),
        scenes=(
            Scene(
                id=1,
                duration=5,
                location="cemetery",
                characters=("shipper",),
                camera=Camera(shot="wide", movement="drone", lens="35mm"),
                action="walk",
                emotion="fear",
                dialogue="Có ai không?",
                image_prompt="a driver",
                video_prompt="walks",
            ),
        ),
    )


class _FakeBuilder:
    def __init__(self, movie: Movie) -> None:
        self._movie = movie

    async def build(self, chapter: StoryChapter, *, style: str, genre: str, language: str) -> Movie:
        return self._movie


def _write_chapter(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "title": "Tu Tiên",
                "content": "A shipper meets a ghost.",
                "estimated_duration_seconds": 60,
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))


def test_movie_command_builds_and_saves(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(mc.MovieBuilder, "from_settings", lambda settings: _FakeBuilder(_movie()))
    chapter = tmp_path / "chapter.json"
    _write_chapter(chapter)

    result = runner.invoke(app, ["movie", "--input", str(chapter)])

    assert result.exit_code == 0
    movie_path = tmp_path / "out" / "movie.json"
    assert movie_path.exists()
    data = json.loads(movie_path.read_text(encoding="utf-8"))
    # output validates against the Movie schema (JSON schema validation)
    restored = Movie.model_validate(data)
    assert restored == _movie()
    # exact schema shape spot-checks
    assert data["scenes"][0]["camera"]["movement"] == "drone"
    assert data["characters"][0]["appearance"]["hair"] == "black"
    assert data["scenes"][0]["dialogue"] == "Có ai không?"  # Vietnamese UTF-8 preserved


def test_movie_command_missing_chapter_fails(tmp_path: Path) -> None:
    result = runner.invoke(app, ["movie", "--input", str(tmp_path / "nope.json")])
    assert result.exit_code == 1


def test_movie_command_does_not_touch_other_outputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(mc.MovieBuilder, "from_settings", lambda settings: _FakeBuilder(_movie()))
    chapter = tmp_path / "chapter.json"
    _write_chapter(chapter)

    runner.invoke(app, ["movie", "--input", str(chapter)])

    out = tmp_path / "out"
    # only movie.json is produced by this command
    assert (out / "movie.json").exists()
    assert not (out / "images").exists()
    assert not (out / "audio").exists()
