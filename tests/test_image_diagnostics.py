"""Tests for image-provider diagnostics (``doctor --image``), no real API."""

from __future__ import annotations

import pytest

from ai_video_factory.infrastructure import diagnostics
from ai_video_factory.infrastructure.providers.base.errors import (
    ProviderUnavailableError,
    RateLimitError,
)
from ai_video_factory.infrastructure.providers.image.base.models import ImageGenerationRequest
from ai_video_factory.shared.health import HealthStatus


class _FakeProvider:
    def __init__(self, models: list[str], *, quota_error: Exception | None = None) -> None:
        self._models = models
        self._quota_error = quota_error

    async def models(self) -> list[str]:
        return self._models

    async def probe_generation(self, request: ImageGenerationRequest) -> None:
        if self._quota_error is not None:
            raise self._quota_error


def _by_name(results: list[diagnostics.CheckResult]) -> dict[str, diagnostics.CheckResult]:
    return {result.name: result for result in results}


@pytest.fixture(autouse=True)
def _with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIVF_IMAGE_PROVIDER__PROVIDER", "gemini_imagen")
    monkeypatch.setenv("AIVF_IMAGE_PROVIDER__API_KEY", "test-key")
    monkeypatch.setenv("AIVF_IMAGE_PROVIDER__MODEL", "gemini-2.5-flash-image")


def test_image_checks_all_green(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeProvider(["models/gemini-2.5-flash-image", "models/other"])
    monkeypatch.setattr(diagnostics.ImageProviderFactory, "create", lambda *a, **k: fake)

    results = _by_name(diagnostics.run_image_checks())

    assert results["Configured model"].detail == "gemini-2.5-flash-image"
    assert results["Image provider"].detail == "gemini_imagen"
    assert "global" in results["Region"].detail
    assert results["Authentication"].status is HealthStatus.OK
    assert results["Image API available"].status is HealthStatus.OK
    assert results["Model exists"].status is HealthStatus.OK
    assert results["Quota response"].status is HealthStatus.OK


def test_image_checks_report_429_quota_with_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    error = RateLimitError(
        "rate limit or quota exceeded (HTTP 429); retry in 21s",
        retry_after=21.0,
        context={"status": 429, "detail": "limit: 0, model: gemini-2.5-flash-preview-image"},
    )
    fake = _FakeProvider(["models/gemini-2.5-flash-image"], quota_error=error)
    monkeypatch.setattr(diagnostics.ImageProviderFactory, "create", lambda *a, **k: fake)

    quota = _by_name(diagnostics.run_image_checks())["Quota response"]

    # A 429 quota is a WARN (advisory), so ``doctor --image`` does not exit
    # non-zero over an account/billing limit, but the detail is still surfaced.
    assert quota.status is HealthStatus.WARN
    assert "429" in quota.detail
    assert "Retry-After=21s" in quota.detail
    assert "limit: 0" in quota.detail


def test_image_checks_flag_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeProvider(["models/some-other-model"])
    monkeypatch.setattr(diagnostics.ImageProviderFactory, "create", lambda *a, **k: fake)

    exists = _by_name(diagnostics.run_image_checks())["Model exists"]

    assert exists.status is HealthStatus.FAIL
    assert "not in available models" in exists.detail


def test_image_checks_api_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Down:
        async def models(self) -> list[str]:
            raise ProviderUnavailableError("503")

        async def probe_generation(
            self, request: ImageGenerationRequest
        ) -> None:  # pragma: no cover
            raise AssertionError("should not be reached")

    monkeypatch.setattr(diagnostics.ImageProviderFactory, "create", lambda *a, **k: _Down())

    api = _by_name(diagnostics.run_image_checks())["Image API available"]
    assert api.status is HealthStatus.FAIL


def test_image_checks_warn_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AIVF_IMAGE_PROVIDER__API_KEY", raising=False)

    results = _by_name(diagnostics.run_image_checks())

    assert results["Authentication"].status is HealthStatus.WARN
    assert "no API key" in results["Authentication"].detail
    assert "Image API available" not in results  # stops before contacting the API
