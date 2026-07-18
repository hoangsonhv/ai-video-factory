"""Tests for the Typer CLI (``version`` and ``doctor`` commands)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory import __version__
from ai_video_factory.infrastructure import diagnostics
from ai_video_factory.interface.cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _quiet_file_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep CLI test runs from writing log files into the repository."""
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")


def test_version_command_prints_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_doctor_command_succeeds_when_environment_is_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("AIVF_DATABASE__PATH", str(tmp_path / "db.sqlite"))
    monkeypatch.setattr(diagnostics.shutil, "which", lambda _name: "/usr/bin/ffmpeg")

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "Python version" in result.stdout


def test_doctor_command_fails_when_a_check_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("AIVF_DATABASE__PATH", str(tmp_path / "db.sqlite"))
    monkeypatch.setattr(diagnostics.shutil, "which", lambda _name: None)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
