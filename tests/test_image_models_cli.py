"""Tests for the ``ai-video-factory image-models`` and ``doctor --image`` CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.infrastructure import diagnostics
from ai_video_factory.infrastructure.providers.base.errors import RateLimitError
from ai_video_factory.infrastructure.providers.image.base.models import ImageGenerationRequest
from ai_video_factory.interface.cli import image_commands as ic
from ai_video_factory.interface.cli.app import app

runner = CliRunner()


class _FakeProvider:
    def __init__(self, models: list[str], *, quota_error: Exception | None = None) -> None:
        self._models = models
        self._quota_error = quota_error

    async def models(self) -> list[str]:
        return self._models

    async def probe_generation(self, request: ImageGenerationRequest) -> None:
        if self._quota_error is not None:
            raise self._quota_error


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("AIVF_IMAGE_PROVIDER__API_KEY", "test-key")
    monkeypatch.setenv("AIVF_IMAGE_PROVIDER__MODEL", "gemini-2.5-flash-image")


def test_image_models_lists_and_marks_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeProvider(["models/gemini-2.5-flash-image", "models/gemini-3-pro-image-preview"])
    monkeypatch.setattr(ic.ImageProviderFactory, "create", lambda *a, **k: fake)

    result = runner.invoke(app, ["image-models"])

    assert result.exit_code == 0
    assert "models/gemini-2.5-flash-image" in result.stdout
    assert "models/gemini-3-pro-image-preview" in result.stdout
    assert "(configured)" in result.stdout  # the configured model is marked
    assert "Configured image model" in result.stdout


def test_image_models_handles_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ic.ImageProviderFactory, "create", lambda *a, **k: _FakeProvider([]))

    result = runner.invoke(app, ["image-models"])

    assert result.exit_code == 0
    assert "No models" in result.stdout


def test_doctor_image_runs_image_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeProvider(["models/gemini-2.5-flash-image"])
    monkeypatch.setattr(diagnostics.ImageProviderFactory, "create", lambda *a, **k: fake)

    result = runner.invoke(app, ["doctor", "--image"])

    assert result.exit_code == 0
    assert "Configured model" in result.stdout
    assert "Quota response" in result.stdout


def test_doctor_image_does_not_error_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    # A 429 quota is an advisory (WARN), so the diagnostic command still exits 0.
    error = RateLimitError("429", retry_after=28.0, context={"status": 429, "detail": "limit: 0"})
    fake = _FakeProvider(["models/gemini-2.5-flash-image"], quota_error=error)
    monkeypatch.setattr(diagnostics.ImageProviderFactory, "create", lambda *a, **k: fake)

    result = runner.invoke(app, ["doctor", "--image"])

    assert result.exit_code == 0
    assert "Quota response" in result.stdout
