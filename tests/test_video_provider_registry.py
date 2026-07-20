"""Tests for the video provider registry and its models."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ai_video_factory.errors import ConfigurationError
from ai_video_factory.infrastructure.config.settings import Settings
from ai_video_factory.infrastructure.providers.base.models import ProviderHealth
from ai_video_factory.infrastructure.video.providers.base.models import (
    VideoGenerationRequest,
    VideoGenerationResult,
    VideoJobStatus,
)
from ai_video_factory.infrastructure.video.providers.kling.provider import KlingVideoProvider
from ai_video_factory.infrastructure.video.providers.mock.provider import MockVideoProvider
from ai_video_factory.infrastructure.video.providers.registry import (
    KLING_PROVIDER,
    MOCK_PROVIDER,
    VideoProviderRegistry,
    build_default_registry,
)
from ai_video_factory.shared.health import HealthStatus


class _FakeProvider:
    """A minimal structural implementation of the VideoProvider protocol."""

    def __init__(self, name: str = "fake", status: HealthStatus = HealthStatus.OK) -> None:
        self._name = name
        self._status = status

    @property
    def name(self) -> str:
        return self._name

    def supported_models(self) -> list[str]:
        return ["fake-v1", "fake-v2"]

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(status=self._status, detail="fake")

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        return VideoGenerationResult(
            scene_id=request.scene_id,
            provider=self._name,
            model="fake-v1",
            status=VideoJobStatus.COMPLETED,
        )


def _registry_with(*providers: _FakeProvider) -> VideoProviderRegistry:
    registry = VideoProviderRegistry()
    for provider in providers:
        registry.register(provider.name, lambda _s, _d, p=provider: p)  # type: ignore[misc]
    return registry


def _settings(provider: str = MOCK_PROVIDER) -> Settings:
    return Settings.model_validate({"video_provider": {"provider": provider}})


# --- registration ----------------------------------------------------------


def test_register_exposes_the_provider_by_name() -> None:
    registry = _registry_with(_FakeProvider())

    assert registry.names == ["fake"]
    assert registry.is_registered("fake")
    assert not registry.is_registered("veo")


def test_names_are_sorted() -> None:
    registry = _registry_with(_FakeProvider("zeta"), _FakeProvider("alpha"))

    assert registry.names == ["alpha", "zeta"]


def test_lookup_is_case_and_space_insensitive() -> None:
    registry = _registry_with(_FakeProvider())

    assert registry.is_registered("  FAKE ")
    assert registry.create("  FAKE ", _settings(), Path("out")).name == "fake"


def test_registering_a_duplicate_name_raises() -> None:
    registry = _registry_with(_FakeProvider())

    with pytest.raises(ConfigurationError, match="already registered"):
        registry.register("fake", lambda _s, _d: _FakeProvider())


def test_registering_a_blank_name_raises() -> None:
    with pytest.raises(ConfigurationError, match="must not be blank"):
        VideoProviderRegistry().register("  ", lambda _s, _d: _FakeProvider())


# --- creation --------------------------------------------------------------


def test_create_unknown_provider_raises_and_lists_the_supported_ones() -> None:
    registry = _registry_with(_FakeProvider())

    with pytest.raises(ConfigurationError, match="unsupported video provider"):
        registry.create("veo", _settings(), Path("out"))


def test_create_on_an_empty_registry_reports_none_supported() -> None:
    with pytest.raises(ConfigurationError, match=r"supported: \(none\)"):
        VideoProviderRegistry().create("mock", _settings(), Path("out"))


def test_create_default_uses_the_configured_provider() -> None:
    registry = _registry_with(_FakeProvider("fake"), _FakeProvider("other"))

    provider = registry.create_default(_settings("other"), Path("out"))

    assert provider.name == "other"


def test_create_default_with_an_unregistered_provider_raises() -> None:
    registry = _registry_with(_FakeProvider())

    with pytest.raises(ConfigurationError):
        registry.create_default(_settings("kling"), Path("out"))


# --- health check ----------------------------------------------------------


def test_health_check_reports_every_provider_and_flags_the_default() -> None:
    registry = _registry_with(
        _FakeProvider("alpha"), _FakeProvider("beta", status=HealthStatus.FAIL)
    )

    statuses = asyncio.run(registry.health_check(_settings("beta"), Path("out")))

    assert [status.name for status in statuses] == ["alpha", "beta"]
    assert [status.is_default for status in statuses] == [False, True]
    assert statuses[1].health.status is HealthStatus.FAIL
    assert statuses[0].models == ("fake-v1", "fake-v2")


def test_health_check_of_an_empty_registry_is_empty() -> None:
    assert asyncio.run(VideoProviderRegistry().health_check(_settings(), Path("out"))) == []


# --- the shipped registry --------------------------------------------------


def test_default_registry_ships_the_mock_and_kling_drivers() -> None:
    assert build_default_registry().names == [KLING_PROVIDER, MOCK_PROVIDER]


def test_default_registry_integrates_no_unapproved_provider() -> None:
    """Kling was approved in Sprint 021; the rest still are not."""
    registry = build_default_registry()

    for forbidden in ("veo", "runway", "hailuo", "sora"):
        assert not registry.is_registered(forbidden)


def test_mock_remains_the_default_so_the_cli_needs_no_paid_key(tmp_path: Path) -> None:
    provider = build_default_registry().create_default(_settings(), tmp_path)

    assert isinstance(provider, MockVideoProvider)
    assert provider.supported_models() == ["mock-slideshow"]


def test_default_registry_builds_kling_when_configured(tmp_path: Path) -> None:
    provider = build_default_registry().create_default(_settings(KLING_PROVIDER), tmp_path)

    assert isinstance(provider, KlingVideoProvider)
    assert provider.name == "kling"


def test_build_default_registry_returns_a_fresh_instance() -> None:
    first = build_default_registry()
    first.register("extra", lambda _s, _d: _FakeProvider("extra"))

    # no global mutable state
    assert build_default_registry().names == [KLING_PROVIDER, MOCK_PROVIDER]
