"""Gemini implementation of the :class:`LLMProvider` protocol.

Orchestrates the low-level client with a timeout and retry policy, translates
timeouts into the provider error hierarchy, and normalizes results into an
:class:`LLMResponse`. Vendor specifics live in :mod:`.client`.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from ai_video_factory.infrastructure.config.settings import ProviderSettings
from ai_video_factory.infrastructure.providers.base.errors import (
    AIProviderError,
    AuthenticationError,
)
from ai_video_factory.infrastructure.providers.base.errors import (
    TimeoutError as ProviderTimeoutError,
)
from ai_video_factory.infrastructure.providers.base.models import (
    LLMRequest,
    LLMResponse,
    ProviderHealth,
    RawCompletion,
    TokenUsage,
)
from ai_video_factory.infrastructure.providers.base.retry import RetryPolicy
from ai_video_factory.infrastructure.providers.gemini.client import GeminiClient, RealGeminiClient
from ai_video_factory.shared.health import HealthStatus

PROVIDER_NAME = "gemini"


class GeminiProvider:
    """LLM provider backed by Google Gemini."""

    def __init__(
        self,
        settings: ProviderSettings,
        *,
        client: GeminiClient | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._model = settings.model
        self._timeout = settings.timeout
        self._clock = clock
        self._retry = RetryPolicy(max_retries=settings.retry_count)
        if client is not None:
            self._client: GeminiClient | None = client
        elif settings.api_key is not None:
            self._client = RealGeminiClient(settings.api_key.get_secret_value())
        else:
            self._client = None

    async def generate(self, request: LLMRequest) -> LLMResponse:
        client = self._require_client()
        model = request.model or self._model
        start = self._clock()
        raw = await self._retry.run(lambda: self._complete(client, request, model))
        latency = self._clock() - start
        usage = TokenUsage(
            prompt_tokens=raw.prompt_tokens,
            completion_tokens=raw.completion_tokens,
            total_tokens=raw.total_tokens,
        )
        return LLMResponse(
            content=raw.content,
            finish_reason=raw.finish_reason,
            usage=usage,
            provider=PROVIDER_NAME,
            model=model,
            latency=latency,
            raw_response=raw.raw,
        )

    async def count_tokens(self, text: str, *, model: str | None = None) -> int:
        client = self._require_client()
        return await client.count_tokens(text, model=model or self._model)

    async def models(self) -> list[str]:
        client = self._require_client()
        return await client.list_models()

    async def health_check(self) -> ProviderHealth:
        if self._client is None:
            return ProviderHealth(status=HealthStatus.WARN, detail="API key not configured")
        try:
            await self._client.list_models()
        except AIProviderError as exc:
            return ProviderHealth(status=HealthStatus.FAIL, detail=str(exc))
        return ProviderHealth(status=HealthStatus.OK, detail=f"reachable (model={self._model})")

    async def _complete(
        self, client: GeminiClient, request: LLMRequest, model: str
    ) -> RawCompletion:
        try:
            return await asyncio.wait_for(
                client.complete(request, model=model), timeout=self._timeout
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError(f"Gemini request timed out after {self._timeout}s") from exc

    def _require_client(self) -> GeminiClient:
        if self._client is None:
            raise AuthenticationError("Gemini API key is not configured")
        return self._client
