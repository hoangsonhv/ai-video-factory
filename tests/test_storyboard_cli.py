"""Tests for the ``ai-video-factory storyboard`` CLI command (no provider calls)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.domain.value_objects.director import DirectedMovie, DirectedScene, Shot
from ai_video_factory.domain.value_objects.movie import Location
from ai_video_factory.domain.value_objects.storyboard import Storyboard
from ai_video_factory.interface.cli.app import app

runner = CliRunner()

_SRT = (
    "1\n00:00:00,000 --> 00:00:02,500\nNgày ấy trời rất trong.\n\n"
    "2\n00:00:02,500 --> 00:00:06,000\nAnh bước lên vách đá.\n\n"
    "3\n00:00:06,000 --> 00:00:09,000\nThanh kiếm rực sáng.\n"
)


def _shot(shot_id: int, duration: int = 3) -> Shot:
    return Shot(
        id=shot_id,
        duration=duration,
        camera="medium shot",
        camera_motion="slow push in",
        lens="50mm",
        framing="rule of thirds",
        subject="lin_tian",
        action="draws a sword",
        expression="resolve hardening",
        environment_motion="embers drifting",
        lighting="hard key",
        transition="cut",
        video_prompt="a composed video prompt",
    )


def _movie(scene_count: int = 2, shots_per_scene: int = 2) -> DirectedMovie:
    return DirectedMovie(
        title="Tu Tiên",
        style="cinematic",
        duration=60,
        locations=(Location(id="cliff", name="Cliff", description="sunrise"),),
        scenes=tuple(
            DirectedScene(
                id=index,
                duration=shots_per_scene * 3,
                location="cliff",
                characters=("lin_tian",),
                emotion="resolve",
                shots=tuple(_shot(n + 1) for n in range(shots_per_scene)),
            )
            for index in range(1, scene_count + 1)
        ),
    )


def _write_movie(path: Path, movie: DirectedMovie | None = None) -> Path:
    path.write_text(
        json.dumps((movie or _movie()).model_dump(), ensure_ascii=False), encoding="utf-8"
    )
    return path


def _write_library(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "characters": [
                    {
                        "id": "lin_tian",
                        "master_prompt": "Lâm Thiên, long black hair",
                        "negative_prompt": "inconsistent face",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _write_narration(out: Path) -> None:
    (out / "subtitles").mkdir(parents=True, exist_ok=True)
    (out / "subtitles" / "narration.srt").write_text(_SRT, encoding="utf-8")
    (out / "audio").mkdir(parents=True, exist_ok=True)
    (out / "audio" / "metadata.json").write_text(
        json.dumps({"duration": 9.0, "voice": "Kore"}), encoding="utf-8"
    )


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))


# --- happy path ------------------------------------------------------------


def test_storyboard_writes_a_schema_valid_file(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie_directed.json")
    _write_narration(tmp_path / "out")

    result = runner.invoke(app, ["storyboard", "--movie", str(movie)])

    assert result.exit_code == 0
    path = tmp_path / "out" / "storyboard.json"
    storyboard = Storyboard.model_validate(json.loads(path.read_text(encoding="utf-8")))

    assert storyboard.shot_count == 4
    assert storyboard.scene_count == 2
    assert storyboard.total_duration == 12.0


def test_the_timeline_is_contiguous(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie_directed.json")

    runner.invoke(app, ["storyboard", "--movie", str(movie)])

    data = json.loads((tmp_path / "out" / "storyboard.json").read_text(encoding="utf-8"))
    ends = [shot["speech_end"] for shot in data["shots"]]
    starts = [shot["speech_start"] for shot in data["shots"]]

    assert starts[0] == 0.0
    assert starts[1:] == ends[:-1]  # each shot starts where the previous ended


def test_narration_is_mapped_onto_the_shots(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie_directed.json")
    _write_narration(tmp_path / "out")

    runner.invoke(app, ["storyboard", "--movie", str(movie)])

    data = json.loads((tmp_path / "out" / "storyboard.json").read_text(encoding="utf-8"))
    assert "Ngày ấy trời rất trong." in data["shots"][0]["subtitle"]  # UTF-8 preserved
    assert data["shots"][3]["subtitle"] == ""  # 9-12s: the narration has finished


def test_audio_segments_reference_the_narration_track(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie_directed.json")
    _write_narration(tmp_path / "out")

    runner.invoke(app, ["storyboard", "--movie", str(movie)])

    data = json.loads((tmp_path / "out" / "storyboard.json").read_text(encoding="utf-8"))
    segment = data["shots"][1]["audio_segment"]

    assert segment["source"].endswith("narration.mp3")
    assert (segment["start"], segment["end"]) == (3.0, 6.0)


def test_the_character_library_reaches_the_image_prompts(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie_directed.json")
    _write_library(tmp_path / "out" / "character_library.json")

    runner.invoke(app, ["storyboard", "--movie", str(movie)])

    data = json.loads((tmp_path / "out" / "storyboard.json").read_text(encoding="utf-8"))
    assert "Lâm Thiên" in data["shots"][0]["image_prompt"]


def test_an_explicit_subtitle_path_is_honoured(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie_directed.json")
    elsewhere = tmp_path / "custom.srt"
    elsewhere.write_text(_SRT, encoding="utf-8")

    result = runner.invoke(
        app, ["storyboard", "--movie", str(movie), "--subtitles", str(elsewhere)]
    )

    assert result.exit_code == 0
    data = json.loads((tmp_path / "out" / "storyboard.json").read_text(encoding="utf-8"))
    assert data["shots"][0]["subtitle"]


def test_the_source_movie_is_left_untouched(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie_directed.json")
    before = movie.read_text(encoding="utf-8")

    runner.invoke(app, ["storyboard", "--movie", str(movie)])

    assert movie.read_text(encoding="utf-8") == before


def test_storyboard_touches_no_other_output(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie_directed.json")

    runner.invoke(app, ["storyboard", "--movie", str(movie)])

    assert [p.name for p in (tmp_path / "out").iterdir()] == ["storyboard.json"]


# --- warnings and failures -------------------------------------------------


def test_missing_narration_is_reported_but_not_fatal(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie_directed.json")

    result = runner.invoke(app, ["storyboard", "--movie", str(movie)])

    assert result.exit_code == 0
    assert "no narration" in result.stdout
    assert (tmp_path / "out" / "storyboard.json").exists()


def test_timeline_drift_is_reported(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie_directed.json")  # 12s of shots
    _write_narration(tmp_path / "out")  # 9s of narration

    result = runner.invoke(app, ["storyboard", "--movie", str(movie)])

    assert "longer than the narration" in result.stdout


def test_a_missing_movie_fails_cleanly(tmp_path: Path) -> None:
    result = runner.invoke(app, ["storyboard", "--movie", str(tmp_path / "nope.json")])

    assert result.exit_code == 1
    assert "directed movie not found" in result.stdout


def test_an_invalid_movie_fails_cleanly(tmp_path: Path) -> None:
    bad = tmp_path / "movie_directed.json"
    bad.write_text("{not json", encoding="utf-8")

    result = runner.invoke(app, ["storyboard", "--movie", str(bad)])

    assert result.exit_code == 1
    assert "invalid JSON" in result.stdout


def test_an_undirected_movie_is_rejected_with_guidance(tmp_path: Path) -> None:
    """A movie whose scenes have no shots means `director` has not run."""
    movie = DirectedMovie(title="x", duration=10, scenes=(DirectedScene(id=1, duration=5),))
    path = _write_movie(tmp_path / "movie_directed.json", movie)

    result = runner.invoke(app, ["storyboard", "--movie", str(path)])

    assert result.exit_code == 1
    assert "run `director`" in result.stdout
    assert not (tmp_path / "out" / "storyboard.json").exists()


def test_the_existing_commands_still_register() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("movie", "character", "director", "storyboard", "compose", "video"):
        assert command in result.stdout


def test_mistimed_subtitles_are_flagged(tmp_path: Path) -> None:
    """ASR-derived cue times can drift; a silently misaligned storyboard is worse."""
    movie = _write_movie(tmp_path / "movie_directed.json")
    out = tmp_path / "out"
    _write_narration(out)
    # the .srt claims 60s of speech while the audio metadata says 9s
    (out / "subtitles" / "narration.srt").write_text(
        "1\n00:00:00,000 --> 00:01:00,000\na very long cue\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["storyboard", "--movie", str(movie)])

    assert result.exit_code == 0
    assert "mistimed" in result.stdout


def test_matching_subtitle_timings_are_not_flagged(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie_directed.json")
    _write_narration(tmp_path / "out")  # srt spans 9s, audio metadata says 9s

    result = runner.invoke(app, ["storyboard", "--movie", str(movie)])

    assert "mistimed" not in result.stdout
