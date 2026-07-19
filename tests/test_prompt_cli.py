"""Tests for the ``factory prompt`` CLI commands."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.interface.cli.app import app

runner = CliRunner()
_REPO_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_PROMPTS__ROOT", str(_REPO_PROMPTS))


def test_prompt_list() -> None:
    result = runner.invoke(app, ["prompt", "list"])
    assert result.exit_code == 0
    assert "story/idea" in result.stdout


def test_prompt_show() -> None:
    result = runner.invoke(app, ["prompt", "show", "story/idea"])
    assert result.exit_code == 0
    assert "{{ topic }}" in result.stdout


def test_prompt_validate() -> None:
    result = runner.invoke(app, ["prompt", "validate"])
    assert result.exit_code == 0
    assert "story/idea" in result.stdout


def test_prompt_render_with_variables() -> None:
    result = runner.invoke(
        app,
        [
            "prompt",
            "render",
            "story/idea",
            "--var",
            "topic=Tu tiên",
            "--var",
            "style=Trung Quốc",
            "--var",
            "target_platform=tiktok",
            "--var",
            "language=vi",
            "--var",
            "count=10",
        ],
    )
    assert result.exit_code == 0
    assert "Tu tiên" in result.stdout
    assert "Trung Quốc" in result.stdout


def test_prompt_render_missing_variable_fails() -> None:
    result = runner.invoke(app, ["prompt", "render", "story/idea", "--var", "topic=x"])
    assert result.exit_code == 1


def test_prompt_show_unknown_fails() -> None:
    result = runner.invoke(app, ["prompt", "show", "story/does-not-exist"])
    assert result.exit_code == 1
