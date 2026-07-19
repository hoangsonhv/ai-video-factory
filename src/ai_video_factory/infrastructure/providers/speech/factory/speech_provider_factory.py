"""Speech provider factory — selects the active TTS provider from config.

The only place that maps a config ``provider`` string to a concrete speech
provider. Adding a future provider means registering one builder here; no
existing code changes (ADR-005, OCP). If the speech API key is unset, the LLM
provider's key is reused (both use the Gemini API).
"""

from __future__ import annotations

from collections.abc import Callable

from ai_video_factory.errors import ConfigurationError
from ai_video_factory.infrastructure.config.settings import Settings, SpeechProviderSettings
from ai_video_factory.infrastructure.media.audio_storage import AudioStorage
from ai_video_factory.infrastructure.providers.speech.base.provider import SpeechProvider
from ai_video_factory.infrastructure.providers.speech.gemini.provider import GeminiSpeechProvider

_BUILDERS: dict[str, Callable[[SpeechProviderSettings, AudioStorage], SpeechProvider]] = {
    "gemini_tts": GeminiSpeechProvider,
}


class SpeechProviderFactory:
    """Creates the configured :class:`SpeechProvider`."""

    @staticmethod
    def create(settings: Settings, storage: AudioStorage) -> SpeechProvider:
        """Build the speech provider selected by configuration.

        Raises:
            ConfigurationError: If the configured provider is not supported.
        """
        speech_settings = settings.speech_provider
        if speech_settings.api_key is None and settings.provider.api_key is not None:
            speech_settings = speech_settings.model_copy(
                update={"api_key": settings.provider.api_key}
            )
        builder = _BUILDERS.get(speech_settings.provider)
        if builder is None:
            supported = ", ".join(sorted(_BUILDERS)) or "(none)"
            raise ConfigurationError(
                f"unsupported speech provider {speech_settings.provider!r}; supported: {supported}"
            )
        return builder(speech_settings, storage)

    @staticmethod
    def supported_providers() -> list[str]:
        """Return the speech provider identifiers this build supports."""
        return sorted(_BUILDERS)
