"""The AI provider contract (structural Protocol).

Every concrete provider (Gemini, and future Claude/OpenAI/OpenRouter/Ollama/
DeepSeek/Qwen) must satisfy this interface. The rest of the system depends on
this protocol, never on a concrete class, so providers are swappable via
configuration (ADR-005).
"""

from __future__ import annotations

from typing import Protocol

from ai_video_factory.infrastructure.providers.base.models import (
    LLMRequest,
    LLMResponse,
    ProviderHealth,
)


class LLMProvider(Protocol):
    """A vendor-neutral large-language-model provider."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Produce a completion for ``request``.

        Raises:
            AIProviderError: On any provider-side failure (translated).
        """
        ...

    async def health_check(self) -> ProviderHealth:
        """Report whether the provider is configured and reachable."""
        ...

    async def count_tokens(self, text: str, *, model: str | None = None) -> int:
        """Return the token count of ``text`` for the given (or default) model."""
        ...

    async def models(self) -> list[str]:
        """Return the model identifiers available from the provider."""
        ...
