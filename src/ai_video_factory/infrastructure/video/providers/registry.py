"""Registry of available video-generation providers.

The one place that maps a config ``provider`` string to a concrete video
provider. Adding a driver means registering one builder — no existing code
changes (ADR-005, OCP).

A registry is *constructed*, never module-global: :func:`build_default_registry`
returns a fresh instance with the shipped drivers registered, so there is no
global mutable state and tests can register fakes in isolation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

from ai_video_factory.errors import ConfigurationError
from ai_video_factory.infrastructure.config.settings import Settings
from ai_video_factory.infrastructure.video.providers.base.models import VideoProviderStatus
from ai_video_factory.infrastructure.video.providers.base.provider import VideoProvider
from ai_video_factory.infrastructure.video.providers.kling.provider import KlingVideoProvider
from ai_video_factory.infrastructure.video.providers.mock.provider import MockVideoProvider

VideoProviderBuilder = Callable[[Settings, Path], VideoProvider]
"""Builds a provider from the settings tree and the clip output directory."""

MOCK_PROVIDER = "mock"
KLING_PROVIDER = "kling"


class VideoProviderRegistry:
    """Holds the known video providers and creates the configured one."""

    def __init__(self) -> None:
        self._builders: dict[str, VideoProviderBuilder] = {}

    def register(self, name: str, builder: VideoProviderBuilder) -> None:
        """Register ``builder`` under ``name``.

        Raises:
            ConfigurationError: If the name is blank or already registered.
        """
        key = name.strip().lower()
        if not key:
            raise ConfigurationError("a video provider name must not be blank")
        if key in self._builders:
            raise ConfigurationError(f"video provider {key!r} is already registered")
        self._builders[key] = builder

    @property
    def names(self) -> list[str]:
        """Every registered provider identifier, sorted."""
        return sorted(self._builders)

    def is_registered(self, name: str) -> bool:
        """Whether ``name`` resolves to a registered provider."""
        return name.strip().lower() in self._builders

    def create(self, name: str, settings: Settings, output_dir: Path) -> VideoProvider:
        """Build the provider registered under ``name``.

        Raises:
            ConfigurationError: If the provider is not registered.
        """
        builder = self._builders.get(name.strip().lower())
        if builder is None:
            supported = ", ".join(self.names) or "(none)"
            raise ConfigurationError(f"unsupported video provider {name!r}; supported: {supported}")
        return builder(settings, output_dir)

    def create_default(self, settings: Settings, output_dir: Path) -> VideoProvider:
        """Build the provider selected by configuration (``VIDEO_PROVIDER``).

        Raises:
            ConfigurationError: If the configured provider is not registered.
        """
        return self.create(settings.video_provider.provider, settings, output_dir)

    async def health_check(self, settings: Settings, output_dir: Path) -> list[VideoProviderStatus]:
        """Health-check every registered provider, concurrently."""
        default = settings.video_provider.provider.strip().lower()
        providers = [self.create(name, settings, output_dir) for name in self.names]
        healths = await asyncio.gather(*(provider.health_check() for provider in providers))
        return [
            VideoProviderStatus(
                name=name,
                is_default=name == default,
                models=tuple(provider.supported_models()),
                health=health,
            )
            for name, provider, health in zip(self.names, providers, healths, strict=True)
        ]


def build_default_registry(
    *, on_progress: Callable[[int, str], None] | None = None
) -> VideoProviderRegistry:
    """Return a registry with every shipped driver registered.

    ``mock`` (local ffmpeg, development) and ``kling`` (Kling AI
    image-to-video) ship today. ``mock`` remains the **default** so the CLI
    works without paid credentials; select Kling with
    ``AIVF_VIDEO_PROVIDER__PROVIDER=kling`` plus an API key.

    ``on_progress`` is forwarded to providers that report generation phases,
    so the interface layer can drive a progress bar.
    """
    registry = VideoProviderRegistry()
    registry.register(
        MOCK_PROVIDER,
        lambda settings, output_dir: MockVideoProvider(
            settings.video_provider, settings.video, output_dir
        ),
    )
    registry.register(
        KLING_PROVIDER,
        lambda settings, output_dir: KlingVideoProvider(
            settings.video_provider, output_dir, on_progress=on_progress
        ),
    )
    return registry
