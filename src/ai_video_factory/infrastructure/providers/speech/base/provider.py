"""The speech provider contract (structural Protocol).

Every concrete TTS provider (Gemini TTS, and future ones) must satisfy this
interface. The rest of the system depends on this protocol, never on a concrete
class, so providers are swappable via configuration (ADR-005).
"""

from __future__ import annotations

from typing import Protocol

from ai_video_factory.infrastructure.providers.base.models import ProviderHealth
from ai_video_factory.infrastructure.providers.speech.base.models import (
    SpeechSynthesisRequest,
    SpeechSynthesisResponse,
)


class SpeechProvider(Protocol):
    """A vendor-neutral text-to-speech provider."""

    async def synthesize(self, request: SpeechSynthesisRequest) -> SpeechSynthesisResponse:
        """Synthesize ``request`` into audio and return where it was saved.

        Raises:
            AIProviderError: On any provider-side failure (translated).
        """
        ...

    async def health_check(self) -> ProviderHealth:
        """Report whether the provider is configured and reachable."""
        ...

    async def list_voices(self) -> list[str]:
        """Return the voice identifiers available from the provider."""
        ...
