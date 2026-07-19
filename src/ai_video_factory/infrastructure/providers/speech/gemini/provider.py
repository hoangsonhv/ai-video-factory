"""Gemini TTS implementation of the :class:`SpeechProvider` protocol.

Orchestrates the low-level client with a timeout and retry policy, saves the
synthesized audio via :class:`AudioStorage`, and returns a
:class:`SpeechSynthesisResponse`. Vendor specifics live in :mod:`.client`.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from ai_video_factory.infrastructure.config.settings import SpeechProviderSettings
from ai_video_factory.infrastructure.media.audio_storage import AudioStorage
from ai_video_factory.infrastructure.providers.base.errors import (
    AIProviderError,
    AuthenticationError,
)
from ai_video_factory.infrastructure.providers.base.errors import (
    TimeoutError as ProviderTimeoutError,
)
from ai_video_factory.infrastructure.providers.base.models import ProviderHealth
from ai_video_factory.infrastructure.providers.base.retry import RetryPolicy
from ai_video_factory.infrastructure.providers.speech.base.models import (
    SpeechSynthesisRequest,
    SpeechSynthesisResponse,
    SynthesizedAudio,
)
from ai_video_factory.infrastructure.providers.speech.gemini.client import (
    GeminiTtsClient,
    RealGeminiTtsClient,
)
from ai_video_factory.shared.health import HealthStatus

PROVIDER_NAME = "gemini_tts"


class GeminiSpeechProvider:
    """Speech provider backed by Google Gemini TTS."""

    def __init__(
        self,
        settings: SpeechProviderSettings,
        storage: AudioStorage,
        *,
        client: GeminiTtsClient | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._model = settings.model
        self._voice = settings.voice
        self._timeout = settings.timeout
        self._storage = storage
        self._clock = clock
        self._retry = RetryPolicy(max_retries=settings.retry_count)
        if client is not None:
            self._client: GeminiTtsClient | None = client
        elif settings.api_key is not None:
            self._client = RealGeminiTtsClient(settings.api_key.get_secret_value())
        else:
            self._client = None

    async def synthesize(self, request: SpeechSynthesisRequest) -> SpeechSynthesisResponse:
        client = self._require_client()
        voice = request.voice or self._voice
        audio = await self._retry.run(lambda: self._call(client, request, voice))
        path = self._storage.save(audio.data)
        return SpeechSynthesisResponse(
            audio_path=path,
            provider=PROVIDER_NAME,
            voice=voice,
            duration_seconds=audio.duration_seconds,
            sample_rate=audio.sample_rate,
            metadata={"language": request.language, "model": self._model},
        )

    async def health_check(self) -> ProviderHealth:
        if self._client is None:
            return ProviderHealth(status=HealthStatus.WARN, detail="API key not configured")
        try:
            await self._client.list_voices()
        except AIProviderError as exc:
            return ProviderHealth(status=HealthStatus.FAIL, detail=str(exc))
        return ProviderHealth(status=HealthStatus.OK, detail=f"configured (model={self._model})")

    async def list_voices(self) -> list[str]:
        return await self._require_client().list_voices()

    async def _call(
        self, client: GeminiTtsClient, request: SpeechSynthesisRequest, voice: str
    ) -> SynthesizedAudio:
        try:
            return await asyncio.wait_for(
                client.synthesize(request, model=self._model, voice=voice), timeout=self._timeout
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError(f"Gemini TTS timed out after {self._timeout}s") from exc

    def _require_client(self) -> GeminiTtsClient:
        if self._client is None:
            raise AuthenticationError("Gemini TTS API key is not configured")
        return self._client
