"""Pollinations implementation of the :class:`ImageProvider` protocol.

A free, key-less image provider for the MVP. Orchestrates the low-level HTTP
client with a timeout and the shared image rate limiter (retry + serialise),
saves the image via :class:`ImageStorage`, and returns an
:class:`ImageGenerationResponse`. HTTP specifics live in :mod:`.client`.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from ai_video_factory.infrastructure.config.settings import ImageProviderSettings
from ai_video_factory.infrastructure.media.image_storage import ImageStorage
from ai_video_factory.infrastructure.providers.base.errors import AIProviderError
from ai_video_factory.infrastructure.providers.base.errors import (
    TimeoutError as ProviderTimeoutError,
)
from ai_video_factory.infrastructure.providers.base.models import ProviderHealth
from ai_video_factory.infrastructure.providers.image.base.models import (
    ImageGenerationRequest,
    ImageGenerationResponse,
)
from ai_video_factory.infrastructure.providers.image.base.rate_limit import ImageRateLimiter
from ai_video_factory.infrastructure.providers.image.pollinations.client import (
    PollinationsClient,
    RealPollinationsClient,
)
from ai_video_factory.shared.health import HealthStatus

PROVIDER_NAME = "pollinations"


class PollinationsImageProvider:
    """Image provider backed by the free Pollinations API (no API key)."""

    def __init__(
        self,
        settings: ImageProviderSettings,
        storage: ImageStorage,
        *,
        client: PollinationsClient | None = None,
        clock: Callable[[], float] = time.monotonic,
        on_rate_limit: Callable[[str], None] | None = None,
    ) -> None:
        self._model = settings.model
        self._timeout = settings.timeout
        self._storage = storage
        self._clock = clock
        self._limiter = ImageRateLimiter(
            max_retries=settings.retry_count, on_rate_limit=on_rate_limit
        )
        # Pollinations needs no credentials, so a client is always available.
        self._client: PollinationsClient = (
            client if client is not None else RealPollinationsClient(timeout=settings.timeout)
        )

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        start = self._clock()
        data = await self._limiter.run(lambda: self._call(request))
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
        try:
            await self._client.list_models()
        except AIProviderError as exc:
            return ProviderHealth(status=HealthStatus.FAIL, detail=str(exc))
        return ProviderHealth(status=HealthStatus.OK, detail=f"reachable (model={self._model})")

    async def models(self) -> list[str]:
        return await self._client.list_models()

    async def probe_generation(self, request: ImageGenerationRequest) -> None:
        """Diagnostic single-shot generation: one call, no retry, no save."""
        await self._client.generate(request, model=self._model)

    async def _call(self, request: ImageGenerationRequest) -> bytes:
        try:
            return await asyncio.wait_for(
                self._client.generate(request, model=self._model), timeout=self._timeout
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                f"Pollinations request timed out after {self._timeout}s"
            ) from exc
