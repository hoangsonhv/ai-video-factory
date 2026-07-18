"""Tests for the environment diagnostics used by ``factory doctor``."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ai_video_factory.infrastructure import diagnostics
from ai_video_factory.infrastructure.diagnostics import (
    check_config_loading,
    check_ffmpeg,
    check_output_writable,
    check_python_version,
    check_sqlite,
    run_all_checks,
)


def test_python_version_reflects_interpreter() -> None:
    result = check_python_version()
    assert result.ok is (sys.version_info[:2] >= (3, 13))


def test_ffmpeg_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostics.shutil, "which", lambda _name: "/usr/bin/ffmpeg")
    result = check_ffmpeg()
    assert result.ok is True
    assert "ffmpeg" in result.detail


def test_ffmpeg_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostics.shutil, "which", lambda _name: None)
    result = check_ffmpeg()
    assert result.ok is False


def test_output_writable(tmp_path: Path) -> None:
    result = check_output_writable(tmp_path / "out")
    assert result.ok is True


def test_sqlite_connectivity(tmp_path: Path) -> None:
    result = check_sqlite(tmp_path / "db" / "factory.db")
    assert result.ok is True


def test_config_loading_returns_settings() -> None:
    result, settings = check_config_loading()
    assert result.ok is True
    assert settings is not None


def test_run_all_checks_includes_expected_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("AIVF_DATABASE__PATH", str(tmp_path / "db.sqlite"))
    names = {result.name for result in run_all_checks()}
    assert {"Python version", "FFmpeg", "Configuration", "Output folder", "SQLite"} <= names
