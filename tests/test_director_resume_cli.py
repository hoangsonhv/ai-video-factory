"""Tests for the director CLI's partial save, report and ``--resume`` flag.

Sprint 022B: one provider request plans the movie. A scene the answer omits is
left unplanned, saved to the partial file, and re-asked by ``--resume``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.domain.value_objects.director import DirectedMovie
from ai_video_factory.domain.value_objects.movie import Camera, Location, Movie, Scene
from ai_video_factory.infrastructure.director.service import PARSE_ATTEMPTS, DirectorService
from ai_video_factory.infrastructure.prompts.service import PromptService
from ai_video_factory.infrastructure.providers.base.errors import ProviderUnavailableError
from ai_video_factory.infrastructure.providers.base.models import (
    LLMRequest,
    LLMResponse,
    TokenUsage,
)
from ai_video_factory.interface.cli import director_commands as dc
from ai_video_factory.interface.cli.app import app

runner = CliRunner()

_SHOT = {
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

# Scene ids the model will silently omit from its answer; mutated per test.
OMITTED: set[int] = set()
# When true the provider raises a transient error on every attempt.
OUTAGE = {"on": False}


class _FlakyProvider:
    """Answers about every requested scene except those listed in ``OMITTED``."""

    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if OUTAGE["on"]:
            raise ProviderUnavailableError("503 service unavailable")
        asked = [
            scene_id
            for scene_id in range(1, 11)
            if f"id {scene_id} " in request.user_prompt and scene_id not in OMITTED
        ]
        return LLMResponse(
            content=json.dumps({"scenes": [{"scene_id": sid, "shots": [_SHOT]} for sid in asked]}),
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            provider="fake",
            model="fake-1",
            latency=0.0,
        )

    @property
    def calls(self) -> int:
        return len(self.requests)


PROVIDER = _FlakyProvider()


def _movie(scene_count: int = 3) -> Movie:
    return Movie(
        title="Tu Tiên",
        style="cinematic",
        duration=60,
        locations=(Location(id="cliff", name="Cliff", description="sunrise"),),
        scenes=tuple(
            Scene(
                id=index,
                duration=5,
                location="cliff",
                camera=Camera(shot="wide shot", movement="drone", lens="35mm"),
                action="walks",
                emotion="resolve",
                video_prompt=f"video {index}",
            )
            for index in range(1, scene_count + 1)
        ),
    )


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))
    OMITTED.clear()
    OUTAGE["on"] = False
    PROVIDER.requests.clear()

    def _from_settings(
        settings: object,
        *,
        on_progress: object = None,
        on_scene_saved: object = None,
    ) -> DirectorService:
        async def _no_sleep(_seconds: float) -> None:
            return None

        return DirectorService(
            PROVIDER,  # type: ignore[arg-type]
            PromptService.create(Path("prompts")),
            on_progress=on_progress,  # type: ignore[arg-type]
            on_scene_saved=on_scene_saved,  # type: ignore[arg-type]
            sleep=_no_sleep,
        )

    monkeypatch.setattr(dc.DirectorService, "from_settings", staticmethod(_from_settings))


def _write_movie(path: Path, movie: Movie | None = None) -> Path:
    path.write_text(
        json.dumps((movie or _movie()).model_dump(), ensure_ascii=False), encoding="utf-8"
    )
    return path


# --- complete runs ---------------------------------------------------------


def test_a_complete_run_writes_the_full_file_and_no_partial(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie.json")

    result = runner.invoke(app, ["director", "--movie", str(movie)])

    assert result.exit_code == 0
    assert (tmp_path / "out" / "movie_directed.json").exists()
    assert not (tmp_path / "out" / "movie_directed.partial.json").exists()


def test_a_complete_run_costs_one_request_per_scene(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie.json")

    runner.invoke(app, ["director", "--movie", str(movie)])

    assert PROVIDER.calls == 3


def test_the_report_shows_directed_failed_and_retry_counts(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie.json")

    result = runner.invoke(app, ["director", "--movie", str(movie)])

    assert "Directed" in result.stdout
    assert "Failed" in result.stdout
    assert "Retry count" in result.stdout


# --- partial save ----------------------------------------------------------


def test_an_omitted_scene_saves_a_partial_file(tmp_path: Path) -> None:
    OMITTED.add(2)
    movie = _write_movie(tmp_path / "movie.json")

    result = runner.invoke(app, ["director", "--movie", str(movie)])

    assert result.exit_code == 1
    assert (tmp_path / "out" / "movie_directed.partial.json").exists()
    assert not (tmp_path / "out" / "movie_directed.json").exists()
    assert "Saved partial" in result.stdout


def test_the_partial_file_keeps_the_planned_scenes(tmp_path: Path) -> None:
    OMITTED.add(2)
    movie = _write_movie(tmp_path / "movie.json")

    runner.invoke(app, ["director", "--movie", str(movie)])

    data = json.loads(
        (tmp_path / "out" / "movie_directed.partial.json").read_text(encoding="utf-8")
    )
    directed = DirectedMovie.model_validate(data)  # still schema-valid

    assert directed.scenes[0].is_planned
    assert directed.scenes[1].shots == ()  # the omitted one
    assert directed.scenes[2].is_planned


def test_the_report_names_the_unplanned_scene(tmp_path: Path) -> None:
    OMITTED.add(2)
    movie = _write_movie(tmp_path / "movie.json")

    result = runner.invoke(app, ["director", "--movie", str(movie)])

    assert "Failed scenes" in result.stdout


def test_a_total_provider_outage_saves_nothing(tmp_path: Path) -> None:
    OUTAGE["on"] = True
    movie = _write_movie(tmp_path / "movie.json")

    result = runner.invoke(app, ["director", "--movie", str(movie)])

    assert result.exit_code == 1
    assert not (tmp_path / "out" / "movie_directed.partial.json").exists()
    assert not (tmp_path / "out" / "movie_directed.json").exists()


def test_an_outage_never_crashes_the_command(tmp_path: Path) -> None:
    OUTAGE["on"] = True
    movie = _write_movie(tmp_path / "movie.json")

    result = runner.invoke(app, ["director", "--movie", str(movie)])

    assert result.exception is None or isinstance(result.exception, SystemExit)
    # Every scene fails on its own now, so the run reports the outcome rather
    # than aborting with an error the moment the first request dies.
    assert "No scene could be directed" in result.stdout


# --- resume ----------------------------------------------------------------


def test_resume_only_re_asks_the_unplanned_scene(tmp_path: Path) -> None:
    OMITTED.add(2)
    movie = _write_movie(tmp_path / "movie.json")
    runner.invoke(app, ["director", "--movie", str(movie)])
    OMITTED.clear()
    PROVIDER.requests.clear()

    result = runner.invoke(app, ["director", "--movie", str(movie), "--resume"])

    assert result.exit_code == 0
    assert PROVIDER.calls == 1  # only the one unplanned scene is re-asked
    prompt = PROVIDER.requests[0].user_prompt
    assert "id 2 " in prompt
    assert "id 1 " not in prompt  # already directed, not re-sent


def test_resume_promotes_the_partial_to_the_final_file(tmp_path: Path) -> None:
    OMITTED.add(2)
    movie = _write_movie(tmp_path / "movie.json")
    runner.invoke(app, ["director", "--movie", str(movie)])
    OMITTED.clear()

    runner.invoke(app, ["director", "--movie", str(movie), "--resume"])

    directed_path = tmp_path / "out" / "movie_directed.json"
    assert directed_path.exists()
    # the stale partial is removed once the run is whole again
    assert not (tmp_path / "out" / "movie_directed.partial.json").exists()
    directed = DirectedMovie.model_validate(json.loads(directed_path.read_text(encoding="utf-8")))
    assert all(scene.is_planned for scene in directed.scenes)


def test_resume_preserves_the_previously_directed_scenes(tmp_path: Path) -> None:
    OMITTED.add(2)
    movie = _write_movie(tmp_path / "movie.json")
    runner.invoke(app, ["director", "--movie", str(movie)])
    before = json.loads(
        (tmp_path / "out" / "movie_directed.partial.json").read_text(encoding="utf-8")
    )
    OMITTED.clear()

    runner.invoke(app, ["director", "--movie", str(movie), "--resume"])

    after = json.loads((tmp_path / "out" / "movie_directed.json").read_text(encoding="utf-8"))
    assert after["scenes"][0] == before["scenes"][0]
    assert after["scenes"][2] == before["scenes"][2]


def test_resume_with_nothing_to_resume_from_directs_everything(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie.json")

    result = runner.invoke(app, ["director", "--movie", str(movie), "--resume"])

    assert result.exit_code == 0
    assert "nothing to resume from" in result.stdout
    assert PROVIDER.calls == 3


def test_resume_can_fail_again_and_leaves_the_partial_intact(tmp_path: Path) -> None:
    """The model omits scene 2 again, so the resume answer covers nothing."""
    OMITTED.add(2)
    movie = _write_movie(tmp_path / "movie.json")
    runner.invoke(app, ["director", "--movie", str(movie)])
    partial = tmp_path / "out" / "movie_directed.partial.json"
    before = partial.read_text(encoding="utf-8")
    PROVIDER.requests.clear()

    result = runner.invoke(app, ["director", "--movie", str(movie), "--resume"])

    assert result.exit_code == 1
    # the one unplanned scene is re-asked, and still cannot be had
    assert PROVIDER.calls == PARSE_ATTEMPTS
    # the earlier progress is left exactly as it was
    assert json.loads(partial.read_text(encoding="utf-8")) == json.loads(before)


def test_resume_from_a_complete_run_calls_nothing(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie.json")
    runner.invoke(app, ["director", "--movie", str(movie)])
    PROVIDER.requests.clear()

    result = runner.invoke(app, ["director", "--movie", str(movie), "--resume"])

    assert result.exit_code == 0
    assert PROVIDER.calls == 0


def test_a_corrupt_partial_fails_cleanly(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie.json")
    partial = tmp_path / "out" / "movie_directed.partial.json"
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text("{not json", encoding="utf-8")

    result = runner.invoke(app, ["director", "--movie", str(movie), "--resume"])

    assert result.exit_code == 1
    assert "invalid JSON" in result.stdout
