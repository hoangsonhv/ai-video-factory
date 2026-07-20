"""Gemini implementation of the :class:`TranscriptionProvider` protocol.

Orchestrates the low-level client with a timeout and retry policy and returns a
:class:`TranscriptionResult`. Vendor specifics live in :mod:`.client`.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from ai_video_factory.infrastructure.config.settings import TranscriptionProviderSettings
from ai_video_factory.infrastructure.providers.base.errors import AuthenticationError
from ai_video_factory.infrastructure.providers.base.errors import (
    TimeoutError as ProviderTimeoutError,
)
from ai_video_factory.infrastructure.providers.base.models import ProviderHealth
from ai_video_factory.infrastructure.providers.base.retry import RetryPolicy
from ai_video_factory.infrastructure.providers.transcription.base.models import (
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionSegment,
)
from ai_video_factory.infrastructure.providers.transcription.gemini.client import (
    GeminiTranscriptionClient,
    RealGeminiTranscriptionClient,
)
from ai_video_factory.shared.health import HealthStatus

PROVIDER_NAME = "gemini_transcription"


class GeminiTranscriptionProvider:
    """Transcription provider backed by Google Gemini audio understanding."""

    def __init__(
        self,
        settings: TranscriptionProviderSettings,
        *,
        client: GeminiTranscriptionClient | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._model = settings.model
        self._timeout = settings.timeout
        self._clock = clock
        self._retry = RetryPolicy(max_retries=settings.retry_count)
        if client is not None:
            self._client: GeminiTranscriptionClient | None = client
        elif settings.api_key is not None:
            self._client = RealGeminiTranscriptionClient(settings.api_key.get_secret_value())
        else:
            self._client = None

    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        client = self._require_client()
        segments = await self._retry.run(lambda: self._call(client, request))
        return TranscriptionResult(
            segments=tuple(segments),
            provider=PROVIDER_NAME,
            language=request.language,
            metadata={"model": self._model},
        )

    async def health_check(self) -> ProviderHealth:
        if self._client is None:
            return ProviderHealth(status=HealthStatus.WARN, detail="API key not configured")
        return ProviderHealth(status=HealthStatus.OK, detail=f"configured (model={self._model})")

    async def _call(
        self, client: GeminiTranscriptionClient, request: TranscriptionRequest
    ) -> list[TranscriptionSegment]:
        try:
            return await asyncio.wait_for(
                client.transcribe(request, model=self._model), timeout=self._timeout
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                f"Gemini transcription timed out after {self._timeout}s"
            ) from exc

    def _require_client(self) -> GeminiTranscriptionClient:
        if self._client is None:
            raise AuthenticationError("Gemini transcription API key is not configured")
        return self._client
