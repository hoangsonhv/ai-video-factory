"""Environment diagnostics for the ``factory doctor`` command (infrastructure).

Lightweight, self-contained health checks that verify the runtime is ready.
Each check reports a tri-state :class:`~ai_video_factory.shared.health.HealthStatus`
(OK / WARN / FAIL). The SQLite check uses the standard library purely to
confirm connectivity; the AI-provider check delegates to the provider layer.
"""

from __future__ import annotations

import asyncio
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ai_video_factory.errors import ConfigurationError, PersistenceError
from ai_video_factory.infrastructure.config.settings import Settings, load_settings
from ai_video_factory.infrastructure.providers.factory.provider_factory import ProviderFactory
from ai_video_factory.shared.health import HealthStatus

MIN_PYTHON: tuple[int, int] = (3, 13)


class CheckResult(BaseModel):
    """Outcome of a single diagnostic check."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: HealthStatus
    detail: str

    @property
    def is_failure(self) -> bool:
        """True only for a hard failure (WARN does not fail the command)."""
        return self.status is HealthStatus.FAIL


def check_python_version() -> CheckResult:
    """Verify the interpreter meets the minimum required version."""
    version = sys.version_info
    ok = (version.major, version.minor) >= MIN_PYTHON
    detail = f"{version.major}.{version.minor}.{version.micro}"
    if not ok:
        detail += f" (requires >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]})"
    return CheckResult(name="Python version", status=_status(ok), detail=detail)


def check_ffmpeg() -> CheckResult:
    """Verify the ``ffmpeg`` executable is discoverable on the PATH."""
    path = shutil.which("ffmpeg")
    if path is None:
        return CheckResult(name="FFmpeg", status=HealthStatus.FAIL, detail="not found on PATH")
    return CheckResult(name="FFmpeg", status=HealthStatus.OK, detail=path)


def check_output_writable(output_dir: Path) -> CheckResult:
    """Verify the configured output folder exists and is writable."""
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output_dir, prefix=".aivf-doctor-"):
            pass
    except OSError as exc:
        return CheckResult(
            name="Output folder", status=HealthStatus.FAIL, detail=f"{output_dir}: {exc}"
        )
    return CheckResult(name="Output folder", status=HealthStatus.OK, detail=str(output_dir))


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
        return CheckResult(name="SQLite", status=HealthStatus.FAIL, detail=str(error))
    return CheckResult(name="SQLite", status=HealthStatus.OK, detail=str(db_path))


def check_config_loading() -> tuple[CheckResult, Settings | None]:
    """Verify the settings tree loads and validates.

    Returns:
        The check result and, on success, the loaded settings (so dependent
        checks can reuse them without loading configuration twice).
    """
    try:
        settings = load_settings()
    except ConfigurationError as exc:
        return CheckResult(name="Configuration", status=HealthStatus.FAIL, detail=str(exc)), None
    detail = f"environment={settings.app.environment}"
    return CheckResult(name="Configuration", status=HealthStatus.OK, detail=detail), settings


def check_ai_provider(settings: Settings) -> CheckResult:
    """Verify the AI provider is configured (API key) and reachable.

    Returns WARN when no API key is configured (the provider is optional at
    this stage) and FAIL when a configured provider cannot be reached.
    """
    try:
        provider = ProviderFactory.create(settings)
    except ConfigurationError as exc:
        return CheckResult(name="AI provider", status=HealthStatus.FAIL, detail=str(exc))
    health = asyncio.run(provider.health_check())
    return CheckResult(
        name="AI provider",
        status=health.status,
        detail=f"{settings.provider.provider}: {health.detail}",
    )


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
        results.append(check_ai_provider(settings))
    return results


def _status(ok: bool) -> HealthStatus:
    return HealthStatus.OK if ok else HealthStatus.FAIL
