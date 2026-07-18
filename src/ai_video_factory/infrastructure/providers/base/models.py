"""Vendor-neutral request/response models for the AI provider layer.

Strongly typed Pydantic models that form the contract between the application
side (which builds requests) and any concrete provider (which fulfils them).
No vendor-specific fields appear here.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from ai_video_factory.shared.health import HealthStatus


class LLMRequest(BaseModel):
    """A single completion request, independent of any provider."""

    model_config = ConfigDict(frozen=True)

    user_prompt: str = Field(min_length=1)
    system_prompt: str | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1024, ge=1)
    model: str | None = None
    json_mode: bool = False
    metadata: Mapping[str, str] = Field(default_factory=dict)


class TokenUsage(BaseModel):
    """Token accounting for a completion."""

    model_config = ConfigDict(frozen=True)

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost: float = Field(default=0.0, ge=0.0)


class LLMResponse(BaseModel):
    """A completed response, normalized across providers."""

    model_config = ConfigDict(frozen=True)

    content: str
    finish_reason: str
    usage: TokenUsage
    provider: str
    model: str
    latency: float = Field(ge=0.0)
    raw_response: Mapping[str, object] = Field(default_factory=dict)


class RawCompletion(BaseModel):
    """Provider-agnostic result returned by a low-level client.

    A concrete client translates its SDK's response into this shape; the
    provider then enriches it into an :class:`LLMResponse`.
    """

    model_config = ConfigDict(frozen=True)

    content: str
    finish_reason: str
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    raw: Mapping[str, object] = Field(default_factory=dict)


class ProviderHealth(BaseModel):
    """Outcome of a provider health check."""

    model_config = ConfigDict(frozen=True)

    status: HealthStatus
    detail: str
