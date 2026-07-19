"""Image provider factory — selects the active image provider from config.

The only place that maps a config ``provider`` string to a concrete image
provider. Adding a future provider means registering one builder here; no
existing code changes (ADR-005, OCP). If the image API key is unset, the LLM
provider's key is reused as a convenience (both use the Gemini API).
"""

from __future__ import annotations

from collections.abc import Callable

from ai_video_factory.errors import ConfigurationError
from ai_video_factory.infrastructure.config.settings import ImageProviderSettings, Settings
from ai_video_factory.infrastructure.media.image_storage import ImageStorage
from ai_video_factory.infrastructure.providers.image.base.provider import ImageProvider
from ai_video_factory.infrastructure.providers.image.gemini.provider import GeminiImagenProvider

_BUILDERS: dict[str, Callable[[ImageProviderSettings, ImageStorage], ImageProvider]] = {
    "gemini_imagen": GeminiImagenProvider,
}


class ImageProviderFactory:
    """Creates the configured :class:`ImageProvider`."""

    @staticmethod
    def create(settings: Settings, storage: ImageStorage) -> ImageProvider:
        """Build the image provider selected by configuration.

        Raises:
            ConfigurationError: If the configured provider is not supported.
        """
        image_settings = settings.image_provider
        if image_settings.api_key is None and settings.provider.api_key is not None:
            image_settings = image_settings.model_copy(
                update={"api_key": settings.provider.api_key}
            )
        builder = _BUILDERS.get(image_settings.provider)
        if builder is None:
            supported = ", ".join(sorted(_BUILDERS)) or "(none)"
            raise ConfigurationError(
                f"unsupported image provider {image_settings.provider!r}; supported: {supported}"
            )
        return builder(image_settings, storage)

    @staticmethod
    def supported_providers() -> list[str]:
        """Return the image provider identifiers this build supports."""
        return sorted(_BUILDERS)
