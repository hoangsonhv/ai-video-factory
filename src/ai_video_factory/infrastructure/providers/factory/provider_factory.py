"""Provider factory — selects the active LLM provider from configuration.

The only place that maps a config ``driver`` string to a concrete provider.
Adding a future provider means registering one builder here; no existing code
changes (ADR-005, OCP).
"""

from __future__ import annotations

from collections.abc import Callable

from ai_video_factory.errors import ConfigurationError
from ai_video_factory.infrastructure.config.settings import (
    ProviderSettings,
    Settings,
    load_settings,
)
from ai_video_factory.infrastructure.providers.base.provider import LLMProvider
from ai_video_factory.infrastructure.providers.gemini.provider import GeminiProvider

_BUILDERS: dict[str, Callable[[ProviderSettings], LLMProvider]] = {
    "gemini": GeminiProvider,
}


class ProviderFactory:
    """Creates the configured :class:`LLMProvider`."""

    @staticmethod
    def create(settings: Settings | None = None) -> LLMProvider:
        """Build the provider selected by configuration.

        Args:
            settings: Settings to read; loaded from the environment if omitted.

        Raises:
            ConfigurationError: If the configured provider is not supported.
        """
        provider_settings = (settings or load_settings()).provider
        builder = _BUILDERS.get(provider_settings.provider)
        if builder is None:
            supported = ", ".join(sorted(_BUILDERS)) or "(none)"
            raise ConfigurationError(
                f"unsupported AI provider {provider_settings.provider!r}; supported: {supported}"
            )
        return builder(provider_settings)

    @staticmethod
    def supported_providers() -> list[str]:
        """Return the provider identifiers this build supports."""
        return sorted(_BUILDERS)
