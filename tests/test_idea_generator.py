"""Tests for the IdeaGenerator service (fake provider, real prompt engine)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from ai_video_factory.domain.value_objects.idea import IdeaBrief
from ai_video_factory.infrastructure.prompts.service import PromptService
from ai_video_factory.infrastructure.providers.base.models import (
    LLMRequest,
    LLMResponse,
    ProviderHealth,
    TokenUsage,
)
from ai_video_factory.infrastructure.story.errors import IdeaParseError
from ai_video_factory.infrastructure.story.idea_generator import IdeaGenerator
from ai_video_factory.shared.health import HealthStatus

_REPO_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
_IDEAS = json.dumps(
    {"ideas": [{"title": f"T{i}", "hook": "H", "summary": "S", "tags": ["a"]} for i in range(10)]}
)


class FakeProvider:
    """LLMProvider double that returns queued contents and records requests."""

    def __init__(self, contents: list[str]) -> None:
        self._contents = contents
        self.requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        content = self._contents[min(len(self.requests) - 1, len(self._contents) - 1)]
        return LLMResponse(
            content=content,
            finish_reason="STOP",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            provider="fake",
            model="fake",
            latency=0.0,
        )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(status=HealthStatus.OK, detail="fake")

    async def count_tokens(self, text: str, *, model: str | None = None) -> int:
        return 0

    async def models(self) -> list[str]:
        return ["fake"]


def _generator(provider: FakeProvider) -> IdeaGenerator:
    return IdeaGenerator(provider, PromptService.create(_REPO_PROMPTS))


def _brief() -> IdeaBrief:
    return IdeaBrief(topic="Tu tiên", style="Trung Quốc", target_platform="tiktok", language="vi")


def test_generate_returns_parsed_ideas() -> None:
    provider = FakeProvider([_IDEAS])
    ideas = asyncio.run(_generator(provider).generate(_brief()))
    assert len(ideas) == 10
    assert ideas[0].title == "T0"


def test_request_uses_json_mode_and_rendered_prompt() -> None:
    provider = FakeProvider([_IDEAS])
    asyncio.run(_generator(provider).generate(_brief()))
    request = provider.requests[0]
    assert request.json_mode is True
    assert "tiktok" in request.user_prompt
    assert "Tu tiên" in request.user_prompt


def test_retry_once_then_succeeds() -> None:
    provider = FakeProvider(["not json", _IDEAS])
    ideas = asyncio.run(_generator(provider).generate(_brief()))
    assert len(ideas) == 10
    assert len(provider.requests) == 2  # initial + one retry


def test_raises_after_retry_exhausted() -> None:
    provider = FakeProvider(["bad", "still bad"])
    with pytest.raises(IdeaParseError):
        asyncio.run(_generator(provider).generate(_brief()))
    assert len(provider.requests) == 2
