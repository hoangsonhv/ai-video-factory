"""Transcription provider factory — selects the active provider from config.

The only place that maps a config ``provider`` string to a concrete
transcription provider. Adding a future provider means registering one builder
here; no existing code changes (ADR-005, OCP). If the transcription API key is
unset, the LLM provider's key is reused (both use the Gemini API).
"""

from __future__ import annotations

from collections.abc import Callable

from ai_video_factory.errors import ConfigurationError
from ai_video_factory.infrastructure.config.settings import (
    Settings,
    TranscriptionProviderSettings,
)
from ai_video_factory.infrastructure.providers.transcription.base.provider import (
    TranscriptionProvider,
)
from ai_video_factory.infrastructure.providers.transcription.gemini.provider import (
    GeminiTranscriptionProvider,
)

_BUILDERS: dict[str, Callable[[TranscriptionProviderSettings], TranscriptionProvider]] = {
    "gemini_transcription": GeminiTranscriptionProvider,
}


class TranscriptionProviderFactory:
    """Creates the configured :class:`TranscriptionProvider`."""

    @staticmethod
    def create(settings: Settings) -> TranscriptionProvider:
        """Build the transcription provider selected by configuration.

        Raises:
            ConfigurationError: If the configured provider is not supported.
        """
        transcription_settings = settings.transcription_provider
        if transcription_settings.api_key is None and settings.provider.api_key is not None:
            transcription_settings = transcription_settings.model_copy(
                update={"api_key": settings.provider.api_key}
            )
        builder = _BUILDERS.get(transcription_settings.provider)
        if builder is None:
            supported = ", ".join(sorted(_BUILDERS)) or "(none)"
            raise ConfigurationError(
                f"unsupported transcription provider {transcription_settings.provider!r}; "
                f"supported: {supported}"
            )
        return builder(transcription_settings)

    @staticmethod
    def supported_providers() -> list[str]:
        """Return the transcription provider identifiers this build supports."""
        return sorted(_BUILDERS)
