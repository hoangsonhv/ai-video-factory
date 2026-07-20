"""The transcription provider contract (structural Protocol).

Every concrete transcription provider (Gemini, and future ones) must satisfy
this interface. The rest of the system depends on this protocol, never on a
concrete class, so providers are swappable via configuration (ADR-005).
"""

from __future__ import annotations

from typing import Protocol

from ai_video_factory.infrastructure.providers.base.models import ProviderHealth
from ai_video_factory.infrastructure.providers.transcription.base.models import (
    TranscriptionRequest,
    TranscriptionResult,
)


class TranscriptionProvider(Protocol):
    """A vendor-neutral speech-to-text (transcription) provider."""

    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        """Transcribe ``request`` audio into timed segments.

        Raises:
            AIProviderError: On any provider-side failure (translated).
        """
        ...

    async def health_check(self) -> ProviderHealth:
        """Report whether the provider is configured and reachable."""
        ...
