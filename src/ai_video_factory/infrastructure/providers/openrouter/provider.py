"""OpenRouter implementation of the :class:`LLMProvider` protocol.

Satisfies the same contract as the Gemini provider — no caller can tell them
apart — so the director (or any stage) is switched by configuration alone
(ADR-005). Orchestrates the low-level client with a per-request timeout and the
shared retry policy, and normalizes results into an :class:`LLMResponse`.
HTTP specifics live in :mod:`.client`.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from ai_video_factory.infrastructure.config.settings import OpenRouterSettings
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
from ai_video_factory.infrastructure.providers.openrouter.client import (
    OpenRouterClient,
    RealOpenRouterClient,
)
from ai_video_factory.shared.health import HealthStatus

PROVIDER_NAME = "openrouter"

# OpenRouter exposes no token-counting endpoint, so `count_tokens` estimates.
# Four characters per token is the usual rule of thumb across these models.
CHARS_PER_TOKEN = 4


class OpenRouterProvider:
    """LLM provider backed by OpenRouter's OpenAI-compatible API."""

    def __init__(
        self,
        settings: OpenRouterSettings,
        *,
        client: OpenRouterClient | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._model = settings.model
        self._timeout = settings.timeout
        self._clock = clock
        self._retry = RetryPolicy(max_retries=settings.retry_count)
        if client is not None:
            self._client: OpenRouterClient | None = client
        elif settings.api_key is not None:
            self._client = RealOpenRouterClient(
                api_key=settings.api_key.get_secret_value(),
                base_url=settings.base_url,
                timeout=settings.timeout,
            )
        else:
            self._client = None

    async def generate(self, request: LLMRequest) -> LLMResponse:
        client = self._require_client()
        model = request.model or self._model
        start = self._clock()
        raw = await self._retry.run(lambda: self._complete(client, request, model))
        latency = self._clock() - start
        return LLMResponse(
            content=raw.content,
            finish_reason=raw.finish_reason,
            usage=TokenUsage(
                prompt_tokens=raw.prompt_tokens,
                completion_tokens=raw.completion_tokens,
                total_tokens=raw.total_tokens,
            ),
            provider=PROVIDER_NAME,
            model=model,
            latency=latency,
            raw_response=raw.raw,
        )

    async def count_tokens(self, text: str, *, model: str | None = None) -> int:
        """Estimate the token count.

        OpenRouter has no counting endpoint, so this is a character-based
        approximation, not an exact count.
        """
        return max(1, len(text) // CHARS_PER_TOKEN) if text else 0

    async def models(self) -> list[str]:
        client = self._require_client()
        return await client.list_models()

    async def health_check(self) -> ProviderHealth:
        if self._client is None:
            return ProviderHealth(
                status=HealthStatus.WARN,
                detail="API key not configured (set AIVF_OPENROUTER_API_KEY)",
            )
        try:
            await self._client.list_models()
        except AIProviderError as exc:
            return ProviderHealth(status=HealthStatus.FAIL, detail=str(exc))
        return ProviderHealth(status=HealthStatus.OK, detail=f"reachable (model={self._model})")

    async def _complete(
        self, client: OpenRouterClient, request: LLMRequest, model: str
    ) -> RawCompletion:
        try:
            return await asyncio.wait_for(
                client.complete(request, model=model), timeout=self._timeout
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                f"OpenRouter request timed out after {self._timeout}s"
            ) from exc

    def _require_client(self) -> OpenRouterClient:
        if self._client is None:
            raise AuthenticationError(
                "OpenRouter API key is not configured (set AIVF_OPENROUTER_API_KEY)"
            )
        return self._client
