"""Tests for ``video generate`` driving the Kling provider (no network)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from ai_video_factory.domain.value_objects.movie import Movie, Scene
from ai_video_factory.infrastructure.video.providers.kling import provider as kling_module
from ai_video_factory.infrastructure.video.providers.kling.client import RealKlingClient
from ai_video_factory.interface.cli.app import app

runner = CliRunner()

BASE_URL = "https://api.klingai.test"


def _movie(scene_count: int = 2) -> Movie:
    return Movie(
        title="Tu Tiên",
        style="cinematic",
        duration=60,
        scenes=tuple(
            Scene(id=index, duration=4, video_prompt=f"scene {index} video")
            for index in range(1, scene_count + 1)
        ),
    )


def _write_movie(path: Path, movie: Movie | None = None) -> Path:
    path.write_text(
        json.dumps((movie or _movie()).model_dump(), ensure_ascii=False), encoding="utf-8"
    )
    return path


def _write_images(images_dir: Path, count: int = 2) -> Path:
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


def _install_transport(
    monkeypatch: pytest.MonkeyPatch, handler: object, *, calls: list[str] | None = None
) -> None:
    """Point every RealKlingClient at an in-process MockTransport."""
    original = RealKlingClient.__init__

    def _patched(self: RealKlingClient, **kwargs: object) -> None:
        kwargs["transport"] = httpx.MockTransport(handler)  # type: ignore[assignment]
        original(self, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(kling_module.RealKlingClient, "__init__", _patched)
    if calls is not None:
        calls.clear()


def _success_handler(calls: list[str]) -> object:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.method == "POST":
            return httpx.Response(
                200,
                json={"code": 0, "data": {"task_id": "task-1", "task_status": "submitted"}},
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
                        "videos": [{"url": "https://cdn.example/x.mp4", "duration": "4"}]
                    },
                },
            },
        )

    return handler


# --- happy path ------------------------------------------------------------


def test_generate_downloads_a_clip_per_scene(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []
    _install_transport(monkeypatch, _success_handler(calls))
    movie = _write_movie(tmp_path / "movie_consistent.json")
    _write_images(tmp_path / "out" / "images")

    result = runner.invoke(app, ["video", "generate", "--movie", str(movie), "--yes"])

    assert result.exit_code == 0
    clips = tmp_path / "out" / "video_clips"
    assert (clips / "shot_001.mp4").read_bytes() == b"mp4-bytes"
    assert (clips / "shot_002.mp4").read_bytes() == b"mp4-bytes"
    assert "Generated 2 clip(s), 0 failed" in result.stdout


def test_generate_writes_the_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_transport(monkeypatch, _success_handler([]))
    movie = _write_movie(tmp_path / "movie_consistent.json")
    _write_images(tmp_path / "out" / "images")

    runner.invoke(app, ["video", "generate", "--movie", str(movie), "--yes"])

    payload = json.loads(
        (tmp_path / "out" / "video_clips" / "manifest.json").read_text(encoding="utf-8")
    )
    assert payload["count"] == 2
    clip = payload["clips"][0]
    assert clip["provider"] == "kling"
    assert clip["model"] == "kling-v1"
    assert clip["status"] == "completed"
    assert clip["remote_job_id"] == "task-1"
    assert clip["duration"] == 4.0
    assert clip["actual_cost"] == 0.0  # no rate configured
    assert clip["estimated_cost"] == 0.0
    assert clip["filename"] == "shot_001.mp4"


def test_generate_submits_polls_and_downloads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []
    _install_transport(monkeypatch, _success_handler(calls))
    movie = _write_movie(tmp_path / "movie_consistent.json", _movie(scene_count=1))
    _write_images(tmp_path / "out" / "images", count=1)

    runner.invoke(app, ["video", "generate", "--movie", str(movie), "--yes"])

    assert calls == [
        "POST /v1/videos/image2video",
        "GET /v1/videos/image2video/task-1",
        "GET /x.mp4",
    ]


def test_the_scene_flag_still_works(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Sprint 020's --scene remains a working alias for --movie."""
    _install_transport(monkeypatch, _success_handler([]))
    movie = _write_movie(tmp_path / "movie_consistent.json", _movie(scene_count=1))
    _write_images(tmp_path / "out" / "images", count=1)

    result = runner.invoke(app, ["video", "generate", "--scene", str(movie), "--yes"])

    assert result.exit_code == 0


def test_an_explicit_images_directory_is_honoured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_transport(monkeypatch, _success_handler([]))
    movie = _write_movie(tmp_path / "movie_consistent.json", _movie(scene_count=1))
    elsewhere = _write_images(tmp_path / "custom_images", count=1)

    result = runner.invoke(
        app, ["video", "generate", "--movie", str(movie), "--images", str(elsewhere), "--yes"]
    )

    assert result.exit_code == 0


# --- failure handling ------------------------------------------------------


def test_a_missing_image_fails_the_scene_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_transport(monkeypatch, _success_handler([]))
    movie = _write_movie(tmp_path / "movie_consistent.json", _movie(scene_count=1))

    result = runner.invoke(app, ["video", "generate", "--movie", str(movie), "--yes"])

    assert result.exit_code == 1
    assert "needs a reference image" in result.stdout
    assert "0 clip(s), 1 failed" in result.stdout


def test_a_provider_outage_does_not_crash(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"message": "service unavailable"})

    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__RETRY_COUNT", "0")
    _install_transport(monkeypatch, handler)
    movie = _write_movie(tmp_path / "movie_consistent.json", _movie(scene_count=1))
    _write_images(tmp_path / "out" / "images", count=1)

    result = runner.invoke(app, ["video", "generate", "--movie", str(movie), "--yes"])

    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "service unavailable" in result.stdout
    assert "0 clip(s), 1 failed" in result.stdout


def test_a_failed_scene_is_recorded_in_the_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": 1101, "message": "insufficient balance"})

    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__RETRY_COUNT", "0")
    _install_transport(monkeypatch, handler)
    movie = _write_movie(tmp_path / "movie_consistent.json", _movie(scene_count=1))
    _write_images(tmp_path / "out" / "images", count=1)

    runner.invoke(app, ["video", "generate", "--movie", str(movie), "--yes"])

    payload = json.loads(
        (tmp_path / "out" / "video_clips" / "manifest.json").read_text(encoding="utf-8")
    )
    assert payload["clips"][0]["status"] == "failed"
    assert payload["clips"][0]["filename"] is None


def test_generate_without_an_api_key_fails_before_any_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("AIVF_VIDEO_PROVIDER__API_KEY", raising=False)
    monkeypatch.setenv("AIVF_VIDEO_PROVIDER__API_KEY", "")
    movie = _write_movie(tmp_path / "movie_consistent.json")

    result = runner.invoke(app, ["video", "generate", "--movie", str(movie), "--yes"])

    assert result.exit_code == 1
    assert "no API key" in result.stdout
    assert not (tmp_path / "out" / "video_clips").exists()


# --- provider discovery ----------------------------------------------------


def test_kling_is_listed_as_a_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    result = runner.invoke(app, ["video", "providers"])

    assert result.exit_code == 0
    assert "kling" in result.stdout
    assert "mock" in result.stdout


def test_doctor_reports_kling_ok_when_configured() -> None:
    result = runner.invoke(app, ["video", "doctor"])

    assert "kling" in result.stdout
    assert "OK" in result.stdout
