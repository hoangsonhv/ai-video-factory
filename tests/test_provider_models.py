"""Tests for the vendor-neutral provider request/response models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_video_factory.infrastructure.providers.base.models import (
    LLMRequest,
    LLMResponse,
    TokenUsage,
)


def test_request_defaults() -> None:
    request = LLMRequest(user_prompt="hello")
    assert request.temperature == 0.7
    assert request.top_p == 1.0
    assert request.max_tokens == 1024
    assert request.json_mode is False
    assert request.system_prompt is None
    assert dict(request.metadata) == {}


def test_request_is_frozen() -> None:
    request = LLMRequest(user_prompt="hello")
    with pytest.raises(ValidationError):
        request.temperature = 1.5  # type: ignore[misc]


def test_request_rejects_out_of_range_temperature() -> None:
    with pytest.raises(ValidationError):
        LLMRequest(user_prompt="hi", temperature=3.0)


def test_request_requires_non_empty_prompt() -> None:
    with pytest.raises(ValidationError):
        LLMRequest(user_prompt="")


def test_response_carries_usage_and_metadata() -> None:
    usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    response = LLMResponse(
        content="hi",
        finish_reason="STOP",
        usage=usage,
        provider="gemini",
        model="gemini-2.0-flash",
        latency=0.42,
    )
    assert response.usage.total_tokens == 15
    assert response.usage.estimated_cost == 0.0
    assert response.provider == "gemini"
