"""Gemini Imagen implementation of the :class:`ImageProvider` protocol.

Orchestrates the low-level client with a timeout and retry policy, saves the
generated image via :class:`ImageStorage`, and returns an
:class:`ImageGenerationResponse`. Vendor specifics live in :mod:`.client`.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from ai_video_factory.infrastructure.config.settings import ImageProviderSettings
from ai_video_factory.infrastructure.media.image_storage import ImageStorage
from ai_video_factory.infrastructure.providers.base.errors import (
    AIProviderError,
    AuthenticationError,
)
from ai_video_factory.infrastructure.providers.base.errors import (
    TimeoutError as ProviderTimeoutError,
)
from ai_video_factory.infrastructure.providers.base.models import ProviderHealth
from ai_video_factory.infrastructure.providers.base.retry import RetryPolicy
from ai_video_factory.infrastructure.providers.image.base.models import (
    ImageGenerationRequest,
    ImageGenerationResponse,
)
from ai_video_factory.infrastructure.providers.image.gemini.client import (
    ImagenClient,
    RealImagenClient,
)
from ai_video_factory.shared.health import HealthStatus

PROVIDER_NAME = "gemini_imagen"


class GeminiImagenProvider:
    """Image provider backed by Google Imagen."""

    def __init__(
        self,
        settings: ImageProviderSettings,
        storage: ImageStorage,
        *,
        client: ImagenClient | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._model = settings.model
        self._timeout = settings.timeout
        self._storage = storage
        self._clock = clock
        self._retry = RetryPolicy(max_retries=settings.retry_count)
        if client is not None:
            self._client: ImagenClient | None = client
        elif settings.api_key is not None:
            self._client = RealImagenClient(settings.api_key.get_secret_value())
        else:
            self._client = None

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        client = self._require_client()
        start = self._clock()
        data = await self._retry.run(lambda: self._call(client, request))
        elapsed = self._clock() - start
        path = self._storage.save(data)
        return ImageGenerationResponse(
            image_path=path,
            provider=PROVIDER_NAME,
            model=self._model,
            generation_time=elapsed,
            metadata={"aspect_ratio": request.aspect_ratio, "seed": request.seed},
        )

    async def health_check(self) -> ProviderHealth:
        if self._client is None:
            return ProviderHealth(status=HealthStatus.WARN, detail="API key not configured")
        try:
            await self._client.list_models()
        except AIProviderError as exc:
            return ProviderHealth(status=HealthStatus.FAIL, detail=str(exc))
        return ProviderHealth(status=HealthStatus.OK, detail=f"reachable (model={self._model})")

    async def models(self) -> list[str]:
        return await self._require_client().list_models()

    async def _call(self, client: ImagenClient, request: ImageGenerationRequest) -> bytes:
        try:
            return await asyncio.wait_for(
                client.generate(request, model=self._model), timeout=self._timeout
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError(f"Imagen request timed out after {self._timeout}s") from exc

    def _require_client(self) -> ImagenClient:
        if self._client is None:
            raise AuthenticationError("Imagen API key is not configured")
        return self._client
