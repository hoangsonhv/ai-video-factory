"""The video provider contract (structural Protocol).

Every concrete video provider — the development ``mock`` today, a commercial
driver whenever one is approved — must satisfy this interface. The rest of the
system depends on this protocol, never on a concrete class, so providers are
swapped by configuration alone (ADR-005).

Expressed as a ``Protocol`` rather than an ABC to match the image, speech and
transcription provider layers: a driver satisfies the contract structurally
and need not import or inherit from this module.
"""

from __future__ import annotations

from typing import Protocol

from ai_video_factory.infrastructure.providers.base.models import ProviderHealth
from ai_video_factory.infrastructure.video.providers.base.models import (
    ClipReferences,
    VideoGenerationRequest,
    VideoGenerationResult,
)


class VideoProvider(Protocol):
    """A vendor-neutral AI video-generation provider."""

    @property
    def name(self) -> str:
        """The driver identifier this provider is registered under."""
        ...

    async def generate(
        self,
        request: VideoGenerationRequest,
        references: ClipReferences | None = None,
    ) -> VideoGenerationResult:
        """Generate the clip for ``request`` and return where it was saved.

        ``references`` offers the character, scene and previous-clip stills a
        provider may condition on to hold consistency across clips. A provider
        that supports none of them ignores it.

        Raises:
            VideoProviderError: On any provider-side failure (translated).
        """
        ...

    def supported_models(self) -> list[str]:
        """Return the model identifiers this provider can render with."""
        ...

    async def health_check(self) -> ProviderHealth:
        """Report whether the provider is configured and able to render."""
        ...
