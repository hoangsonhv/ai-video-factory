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
from ai_video_factory.infrastructure.media.image_storage import ImageStorage
from ai_video_factory.infrastructure.providers.base.errors import (
    AIProviderError,
    AuthenticationError,
    RateLimitError,
)
from ai_video_factory.infrastructure.providers.factory.provider_factory import ProviderFactory
from ai_video_factory.infrastructure.providers.image.base.models import ImageGenerationRequest
from ai_video_factory.infrastructure.providers.image.base.provider import ImageProvider
from ai_video_factory.infrastructure.providers.image.factory.image_provider_factory import (
    ImageProviderFactory,
)
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


def _model_in(configured: str, available: list[str]) -> bool:
    """True if the configured model matches an available id (with/without prefix)."""
    candidates = {configured, f"models/{configured}"}
    stripped = {name.removeprefix("models/") for name in available}
    return bool(candidates & set(available)) or configured in stripped


def _quota_result(error: AIProviderError | None) -> CheckResult:
    """Turn the outcome of the quota probe into a check result.

    A rate limit / quota response is a WARN, not a FAIL: it is an account or
    billing condition (often a free-tier ``limit: 0`` for image generation),
    not a broken setup, so it is surfaced prominently without making the
    diagnostic command itself exit non-zero.
    """
    if error is None:
        return CheckResult(
            name="Quota response",
            status=HealthStatus.OK,
            detail="generation succeeded (quota available)",
        )
    if isinstance(error, RateLimitError):
        detail = str(error.context.get("detail", error))
        retry = f"; Retry-After={error.retry_after:.0f}s" if error.retry_after else ""
        return CheckResult(
            name="Quota response",
            status=HealthStatus.WARN,
            detail=f"HTTP 429 quota exceeded{retry} :: {detail}",
        )
    return CheckResult(name="Quota response", status=HealthStatus.WARN, detail=str(error))


async def _live_image_checks(provider: ImageProvider, configured_model: str) -> list[CheckResult]:
    """Contact the image API once (single event loop): list models, then probe.

    Both async calls share one loop because the vendor client binds its HTTP
    transport to the loop it is first used in; separate ``asyncio.run`` calls
    would reuse a closed loop.
    """
    try:
        available = await provider.models()
    except AuthenticationError as exc:
        return [CheckResult(name="Authentication", status=HealthStatus.FAIL, detail=str(exc))]
    except AIProviderError as exc:
        return [CheckResult(name="Image API available", status=HealthStatus.FAIL, detail=str(exc))]

    exists = _model_in(configured_model, available)
    results = [
        CheckResult(name="Authentication", status=HealthStatus.OK, detail="key accepted"),
        CheckResult(
            name="Image API available",
            status=HealthStatus.OK,
            detail=f"reachable ({len(available)} models)",
        ),
        CheckResult(
            name="Model exists",
            status=HealthStatus.OK if exists else HealthStatus.FAIL,
            detail=configured_model if exists else f"{configured_model} not in available models",
        ),
    ]

    quota_error: AIProviderError | None = None
    request = ImageGenerationRequest(prompt="diagnostic probe", aspect_ratio="1:1")
    try:
        await provider.probe_generation(request)
    except AIProviderError as exc:
        quota_error = exc
    results.append(_quota_result(quota_error))
    return results


def run_image_checks() -> list[CheckResult]:
    """Run image-provider diagnostics for ``doctor --image``.

    Reports the configured model, provider, region, authentication, whether the
    image API is reachable, whether the model exists, and — when a key is
    configured — a live quota probe (a single generation request).
    """
    config_result, settings = check_config_loading()
    results = [config_result]
    if settings is None:
        return results

    image = settings.image_provider
    results.append(
        CheckResult(name="Image provider", status=HealthStatus.OK, detail=image.provider)
    )
    results.append(CheckResult(name="Configured model", status=HealthStatus.OK, detail=image.model))
    results.append(
        CheckResult(name="Region", status=HealthStatus.OK, detail="global (Gemini Developer API)")
    )

    has_key = image.api_key is not None or settings.provider.api_key is not None
    if not has_key:
        results.append(
            CheckResult(
                name="Authentication",
                status=HealthStatus.WARN,
                detail="no API key configured (set AIVF_IMAGE_PROVIDER__API_KEY)",
            )
        )
        return results

    storage = ImageStorage(settings.app.output_dir / "images")
    provider = ImageProviderFactory.create(settings, storage)
    results.extend(asyncio.run(_live_image_checks(provider, image.model)))
    return results


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
