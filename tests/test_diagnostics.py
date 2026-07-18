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
from ai_video_factory.shared.health import HealthStatus


def test_python_version_reflects_interpreter() -> None:
    result = check_python_version()
    expected = HealthStatus.OK if sys.version_info[:2] >= (3, 13) else HealthStatus.FAIL
    assert result.status is expected


def test_ffmpeg_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostics.shutil, "which", lambda _name: "/usr/bin/ffmpeg")
    result = check_ffmpeg()
    assert result.status is HealthStatus.OK
    assert "ffmpeg" in result.detail


def test_ffmpeg_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostics.shutil, "which", lambda _name: None)
    result = check_ffmpeg()
    assert result.status is HealthStatus.FAIL
    assert result.is_failure is True


def test_output_writable(tmp_path: Path) -> None:
    result = check_output_writable(tmp_path / "out")
    assert result.status is HealthStatus.OK


def test_sqlite_connectivity(tmp_path: Path) -> None:
    result = check_sqlite(tmp_path / "db" / "factory.db")
    assert result.status is HealthStatus.OK


def test_config_loading_returns_settings() -> None:
    result, settings = check_config_loading()
    assert result.status is HealthStatus.OK
    assert settings is not None


def test_ai_provider_warns_without_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # No AIVF_PROVIDER__API_KEY set (autouse fixture clears AIVF_ env).
    from ai_video_factory.infrastructure.config.settings import Settings
    from ai_video_factory.infrastructure.diagnostics import check_ai_provider

    result = check_ai_provider(Settings(_env_file=None))
    assert result.status is HealthStatus.WARN
    assert result.is_failure is False


def test_run_all_checks_includes_expected_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("AIVF_DATABASE__PATH", str(tmp_path / "db.sqlite"))
    names = {result.name for result in run_all_checks()}
    assert {
        "Python version",
        "FFmpeg",
        "Configuration",
        "Output folder",
        "SQLite",
        "AI provider",
    } <= names
