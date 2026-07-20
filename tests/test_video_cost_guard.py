"""Tests for the cost guard: plan estimation, --dry-run, --limit, confirmation."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from ai_video_factory.domain.value_objects.movie import Movie, Scene
from ai_video_factory.infrastructure.config.settings import VideoProviderSettings
from ai_video_factory.infrastructure.video.providers.base.models import VideoGenerationRequest
from ai_video_factory.infrastructure.video.providers.cost import (
    build_plan,
    estimate_cost,
)
from ai_video_factory.infrastructure.video.providers.kling import provider as kling_module
from ai_video_factory.infrastructure.video.providers.kling.client import RealKlingClient
from ai_video_factory.interface.cli.app import app

runner = CliRunner()

BASE_URL = "https://api.klingai.test"


def _settings(**overrides: object) -> VideoProviderSettings:
    defaults: dict[str, object] = {"provider": "kling", "model": "kling-v1"}
    defaults.update(overrides)
    return VideoProviderSettings.model_validate(defaults)


def _requests(count: int, duration: float = 5.0) -> list[VideoGenerationRequest]:
    return [
        VideoGenerationRequest(scene_id=index, duration=duration) for index in range(1, count + 1)
    ]


# --- cost estimation (pure) ------------------------------------------------


def test_estimate_cost_multiplies_duration_by_the_rate() -> None:
    assert estimate_cost(5.0, _settings(cost_per_second=0.28)) == 1.4


def test_estimate_cost_is_zero_without_a_configured_rate() -> None:
    assert estimate_cost(5.0, _settings()) == 0.0


def test_plan_totals_every_request() -> None:
    plan = build_plan(_requests(3), _settings(cost_per_second=0.2))

    assert plan.provider == "kling"
    assert plan.model == "kling-v1"
    assert plan.scene_count == 3
    assert plan.jobs == 3
    assert plan.total_duration == 15.0
    assert plan.estimated_cost == 3.0
    assert plan.per_scene == {1: 1.0, 2: 1.0, 3: 1.0}


def test_plan_marks_a_limited_run() -> None:
    plan = build_plan(_requests(2), _settings(), scene_count=8)

    assert plan.jobs == 2
    assert plan.scene_count == 8
    assert plan.limited


def test_plan_of_a_full_run_is_not_limited() -> None:
    assert not build_plan(_requests(3), _settings(), scene_count=3).limited


def test_plan_knows_whether_the_run_is_paid() -> None:
    assert build_plan(_requests(1), _settings(provider="kling")).is_paid
    assert not build_plan(_requests(1), _settings(provider="mock")).is_paid


def test_an_unconfigured_rate_reports_cost_as_unknown_not_free() -> None:
    plan = build_plan(_requests(2), _settings())

    assert plan.estimated_cost == 0.0
    assert not plan.cost_is_known


def test_scene_estimate_falls_back_to_zero() -> None:
    plan = build_plan(_requests(1), _settings(cost_per_second=0.2))

    assert plan.scene_estimate(1) == 1.0
    assert plan.scene_estimate(99) == 0.0


def test_an_empty_plan_is_valid() -> None:
    plan = build_plan([], _settings())

    assert plan.jobs == 0
    assert plan.estimated_cost == 0.0


# --- CLI ------------------------------------------------------------------


def _movie(scene_count: int = 4) -> Movie:
    return Movie(
        title="Tu Tiên",
        style="cinematic",
        duration=60,
        scenes=tuple(
            Scene(id=index, duration=5, video_prompt=f"scene {index}")
            for index in range(1, scene_count + 1)
        ),
    )


def _write_movie(path: Path, movie: Movie | None = None) -> Path:
    path.write_text(
        json.dumps((movie or _movie()).model_dump(), ensure_ascii=False), encoding="utf-8"
    )
    return path


def _write_images(images_dir: Path, count: int = 4) -> Path:
    images_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, count + 1):
        (images_dir / f"{index:03d}.png").write_bytes(b"\x89PNG")
    return images_dir


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__PROVIDER", "kling")
    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__API_KEY", "test-key")
    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__MODEL", "kling-v1")
    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__BASE_URL", BASE_URL)
    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__POLL_INTERVAL", "0.001")
    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__COST_PER_SECOND", "0.2")


def _install_transport(monkeypatch: pytest.MonkeyPatch, calls: list[str]) -> None:
    """Serve a successful Kling exchange and record every request."""

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.method == "POST":
            return httpx.Response(
                200, json={"code": 0, "data": {"task_id": "task-1", "task_status": "submitted"}}
            )
        if request.url.host == "cdn.example":
            return httpx.Response(200, content=b"mp4-bytes")
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "task_id": "task-1",
                    "task_status": "succeed",
                    "task_result": {
                        "videos": [{"url": "https://cdn.example/x.mp4", "duration": "5"}]
                    },
                },
            },
        )

    original = RealKlingClient.__init__

    def _patched(self: RealKlingClient, **kwargs: object) -> None:
        kwargs["transport"] = httpx.MockTransport(handler)  # type: ignore[assignment]
        original(self, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(kling_module.RealKlingClient, "__init__", _patched)


# --- --dry-run -------------------------------------------------------------


def test_dry_run_submits_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[str] = []
    _install_transport(monkeypatch, calls)
    movie = _write_movie(tmp_path / "movie.json")
    _write_images(tmp_path / "out" / "images")

    result = runner.invoke(app, ["video", "generate", "--movie", str(movie), "--dry-run"])

    assert result.exit_code == 0
    assert calls == []  # no HTTP at all
    assert not (tmp_path / "out" / "video_clips").exists()
    assert "nothing was submitted" in result.stdout


def test_dry_run_reports_the_plan(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie.json")

    result = runner.invoke(app, ["video", "generate", "--movie", str(movie), "--dry-run"])

    for expected in ("kling", "kling-v1", "20.0s", "4.00"):
        assert expected in result.stdout


def test_dry_run_needs_no_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__API_KEY", "")
    movie = _write_movie(tmp_path / "movie.json")

    result = runner.invoke(app, ["video", "generate", "--movie", str(movie), "--dry-run"])

    assert result.exit_code == 0
    assert "no API key" not in result.stdout


def test_dry_run_reports_an_unknown_cost_when_no_rate_is_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__COST_PER_SECOND", "0")
    movie = _write_movie(tmp_path / "movie.json")

    result = runner.invoke(app, ["video", "generate", "--movie", str(movie), "--dry-run"])

    assert "unknown" in result.stdout


def test_dry_run_honours_the_limit(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie.json")

    result = runner.invoke(
        app, ["video", "generate", "--movie", str(movie), "--dry-run", "--limit", "2"]
    )

    assert "limited to the first 2" in result.stdout


# --- --limit ---------------------------------------------------------------


def test_limit_submits_only_the_first_n_scenes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []
    _install_transport(monkeypatch, calls)
    movie = _write_movie(tmp_path / "movie.json")
    _write_images(tmp_path / "out" / "images")

    result = runner.invoke(
        app, ["video", "generate", "--movie", str(movie), "--limit", "2", "--yes"]
    )

    assert result.exit_code == 0
    assert sum(1 for call in calls if call.startswith("POST")) == 2
    clips = tmp_path / "out" / "video_clips"
    assert sorted(p.name for p in clips.glob("*.mp4")) == ["shot_001.mp4", "shot_002.mp4"]


def test_limit_larger_than_the_scene_count_is_harmless(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []
    _install_transport(monkeypatch, calls)
    movie = _write_movie(tmp_path / "movie.json", _movie(scene_count=2))
    _write_images(tmp_path / "out" / "images", count=2)

    result = runner.invoke(
        app, ["video", "generate", "--movie", str(movie), "--limit", "99", "--yes"]
    )

    assert result.exit_code == 0
    assert sum(1 for call in calls if call.startswith("POST")) == 2


def test_a_zero_limit_is_rejected(tmp_path: Path) -> None:
    movie = _write_movie(tmp_path / "movie.json")

    result = runner.invoke(
        app, ["video", "generate", "--movie", str(movie), "--limit", "0", "--dry-run"]
    )

    assert result.exit_code != 0


# --- confirmation ----------------------------------------------------------


def test_a_paid_run_prompts_and_declining_submits_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []
    _install_transport(monkeypatch, calls)
    movie = _write_movie(tmp_path / "movie.json")
    _write_images(tmp_path / "out" / "images")

    result = runner.invoke(app, ["video", "generate", "--movie", str(movie)], input="n\n")

    assert result.exit_code == 0
    assert calls == []
    assert "will submit 4 paid AI video job(s)" in result.stdout
    assert "Aborted" in result.stdout


def test_accepting_the_prompt_proceeds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[str] = []
    _install_transport(monkeypatch, calls)
    movie = _write_movie(tmp_path / "movie.json", _movie(scene_count=1))
    _write_images(tmp_path / "out" / "images", count=1)

    result = runner.invoke(app, ["video", "generate", "--movie", str(movie)], input="y\n")

    assert result.exit_code == 0
    assert sum(1 for call in calls if call.startswith("POST")) == 1


def test_the_prompt_defaults_to_no(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Bare Enter must not spend money."""
    calls: list[str] = []
    _install_transport(monkeypatch, calls)
    movie = _write_movie(tmp_path / "movie.json")
    _write_images(tmp_path / "out" / "images")

    result = runner.invoke(app, ["video", "generate", "--movie", str(movie)], input="\n")

    assert calls == []
    assert "Aborted" in result.stdout


def test_a_closed_stdin_declines_rather_than_spending(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Non-interactive (CI, piped) runs must not submit paid jobs unattended."""
    calls: list[str] = []
    _install_transport(monkeypatch, calls)
    movie = _write_movie(tmp_path / "movie.json")
    _write_images(tmp_path / "out" / "images")

    result = runner.invoke(app, ["video", "generate", "--movie", str(movie)], input="")

    assert calls == []
    assert result.exit_code == 0


def test_yes_skips_the_prompt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[str] = []
    _install_transport(monkeypatch, calls)
    movie = _write_movie(tmp_path / "movie.json", _movie(scene_count=1))
    _write_images(tmp_path / "out" / "images", count=1)

    result = runner.invoke(app, ["video", "generate", "--movie", str(movie), "--yes"])

    assert result.exit_code == 0
    assert "Continue?" not in result.stdout
    assert sum(1 for call in calls if call.startswith("POST")) == 1


def test_the_mock_provider_never_prompts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The local mock spends nothing, so it must not nag."""
    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__PROVIDER", "mock")
    movie = _write_movie(tmp_path / "movie.json", _movie(scene_count=1))

    result = runner.invoke(app, ["video", "generate", "--movie", str(movie)], input="")

    assert "Continue?" not in result.stdout


# --- manifest costs --------------------------------------------------------


def test_manifest_records_estimated_and_actual_cost(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_transport(monkeypatch, [])
    movie = _write_movie(tmp_path / "movie.json", _movie(scene_count=2))
    _write_images(tmp_path / "out" / "images", count=2)

    runner.invoke(app, ["video", "generate", "--movie", str(movie), "--yes"])

    payload = json.loads(
        (tmp_path / "out" / "video_clips" / "manifest.json").read_text(encoding="utf-8")
    )
    clip = payload["clips"][0]
    assert clip["estimated_cost"] == 1.0  # 5s x 0.2
    assert clip["actual_cost"] == 1.0
    assert payload["total_estimated_cost"] == 2.0
    assert payload["total_actual_cost"] == 2.0


def test_a_failed_scene_keeps_its_estimate_but_costs_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": 1101, "message": "insufficient balance"})

    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__RETRY_COUNT", "0")
    original = RealKlingClient.__init__

    def _patched(self: RealKlingClient, **kwargs: object) -> None:
        kwargs["transport"] = httpx.MockTransport(handler)  # type: ignore[assignment]
        original(self, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(kling_module.RealKlingClient, "__init__", _patched)
    movie = _write_movie(tmp_path / "movie.json", _movie(scene_count=1))
    _write_images(tmp_path / "out" / "images", count=1)

    runner.invoke(app, ["video", "generate", "--movie", str(movie), "--yes"])

    payload = json.loads(
        (tmp_path / "out" / "video_clips" / "manifest.json").read_text(encoding="utf-8")
    )
    clip = payload["clips"][0]
    assert clip["status"] == "failed"
    assert clip["estimated_cost"] == 1.0
    assert clip["actual_cost"] == 0.0
    assert payload["total_actual_cost"] == 0.0
