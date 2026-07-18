"""Environment diagnostics for the ``factory doctor`` command (infrastructure).

Lightweight, self-contained health checks that verify the runtime is ready.
These are diagnostics only — they do not build the persistence or provider
layers (which arrive in later sprints); the SQLite check uses the standard
library purely to confirm connectivity.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ai_video_factory.errors import ConfigurationError, PersistenceError
from ai_video_factory.infrastructure.config.settings import Settings, load_settings

MIN_PYTHON: tuple[int, int] = (3, 13)


class CheckResult(BaseModel):
    """Outcome of a single diagnostic check."""

    model_config = ConfigDict(frozen=True)

    name: str
    ok: bool
    detail: str


def check_python_version() -> CheckResult:
    """Verify the interpreter meets the minimum required version."""
    version = sys.version_info
    ok = (version.major, version.minor) >= MIN_PYTHON
    detail = f"{version.major}.{version.minor}.{version.micro}"
    if not ok:
        detail += f" (requires >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]})"
    return CheckResult(name="Python version", ok=ok, detail=detail)


def check_ffmpeg() -> CheckResult:
    """Verify the ``ffmpeg`` executable is discoverable on the PATH."""
    path = shutil.which("ffmpeg")
    if path is None:
        return CheckResult(name="FFmpeg", ok=False, detail="not found on PATH")
    return CheckResult(name="FFmpeg", ok=True, detail=path)


def check_output_writable(output_dir: Path) -> CheckResult:
    """Verify the configured output folder exists and is writable."""
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output_dir, prefix=".aivf-doctor-"):
            pass
    except OSError as exc:
        return CheckResult(name="Output folder", ok=False, detail=f"{output_dir}: {exc}")
    return CheckResult(name="Output folder", ok=True, detail=str(output_dir))


def check_sqlite(db_path: Path) -> CheckResult:
    """Verify a SQLite connection can be opened at the configured path."""
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(db_path))
        try:
            connection.execute("SELECT 1")
        finally:
            connection.close()
    except (sqlite3.Error, OSError) as exc:
        error = PersistenceError(
            f"cannot open SQLite database at {db_path}", context={"error": str(exc)}
        )
        return CheckResult(name="SQLite", ok=False, detail=str(error))
    return CheckResult(name="SQLite", ok=True, detail=str(db_path))


def check_config_loading() -> tuple[CheckResult, Settings | None]:
    """Verify the settings tree loads and validates.

    Returns:
        The check result and, on success, the loaded settings (so dependent
        checks can reuse them without loading configuration twice).
    """
    try:
        settings = load_settings()
    except ConfigurationError as exc:
        return CheckResult(name="Configuration", ok=False, detail=str(exc)), None
    detail = f"environment={settings.app.environment}"
    return CheckResult(name="Configuration", ok=True, detail=detail), settings


def run_all_checks() -> list[CheckResult]:
    """Run every diagnostic check and return the collected results.

    Configuration is checked before the checks that depend on it; if it fails,
    the dependent checks are skipped since their inputs are unknown.
    """
    results = [check_python_version(), check_ffmpeg()]
    config_result, settings = check_config_loading()
    results.append(config_result)
    if settings is not None:
        results.append(check_output_writable(settings.app.output_dir))
        results.append(check_sqlite(settings.database.path))
    return results
