"""Provider factory — selects the active LLM provider from configuration.

The only place that maps a config ``driver`` string to a concrete provider.
Adding a future provider means registering one builder here; no existing code
changes (ADR-005, OCP).

The **director** may run on a different provider from the rest of the story
pipeline (``AIVF_DIRECTOR_PROVIDER``), so shot planning can use a model chosen
for structured JSON while story generation stays on its own.
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
from ai_video_factory.infrastructure.providers.openrouter.provider import OpenRouterProvider

GEMINI = "gemini"
OPENROUTER = "openrouter"

_BUILDERS: dict[str, Callable[[ProviderSettings], LLMProvider]] = {
    GEMINI: GeminiProvider,
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
        resolved = settings or load_settings()
        provider_settings = resolved.provider
        if provider_settings.provider == OPENROUTER:
            return OpenRouterProvider(resolved.openrouter)
        builder = _BUILDERS.get(provider_settings.provider)
        if builder is None:
            supported = ", ".join(ProviderFactory.supported_providers())
            raise ConfigurationError(
                f"unsupported AI provider {provider_settings.provider!r}; supported: {supported}"
            )
        return builder(provider_settings)

    @staticmethod
    def create_director(settings: Settings | None = None) -> LLMProvider:
        """Build the provider the **director** should use.

        Falls back to the general provider when ``AIVF_DIRECTOR_PROVIDER`` is
        unset or names the same driver.

        Raises:
            ConfigurationError: If the configured provider is not supported.
        """
        resolved = settings or load_settings()
        driver = (resolved.director_provider or "").strip().lower()
        if not driver:
            return ProviderFactory.create(resolved)
        if driver == OPENROUTER:
            return OpenRouterProvider(resolved.openrouter)
        builder = _BUILDERS.get(driver)
        if builder is None:
            supported = ", ".join(ProviderFactory.supported_providers())
            raise ConfigurationError(
                f"unsupported director provider {driver!r}; supported: {supported}"
            )
        return builder(resolved.provider)

    @staticmethod
    def director_model(settings: Settings) -> str | None:
        """The model the director should request, or ``None`` for the default."""
        driver = (settings.director_provider or "").strip().lower()
        if driver == OPENROUTER:
            return settings.openrouter.model
        return settings.provider.director_model or None

    @staticmethod
    def supported_providers() -> list[str]:
        """Return the provider identifiers this build supports."""
        return sorted({*_BUILDERS, OPENROUTER})
