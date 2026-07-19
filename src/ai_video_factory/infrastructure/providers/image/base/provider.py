"""The image provider contract (structural Protocol).

Every concrete image provider (Gemini Imagen, and future ones) must satisfy
this interface. The rest of the system depends on this protocol, never on a
concrete class, so providers are swappable via configuration (ADR-005).
"""

from __future__ import annotations

from typing import Protocol

from ai_video_factory.infrastructure.providers.base.models import ProviderHealth
from ai_video_factory.infrastructure.providers.image.base.models import (
    ImageGenerationRequest,
    ImageGenerationResponse,
)


class ImageProvider(Protocol):
    """A vendor-neutral image-generation provider."""

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        """Generate an image for ``request`` and return where it was saved.

        Raises:
            AIProviderError: On any provider-side failure (translated).
        """
        ...

    async def health_check(self) -> ProviderHealth:
        """Report whether the provider is configured and reachable."""
        ...

    async def models(self) -> list[str]:
        """Return the model identifiers available from the provider."""
        ...
