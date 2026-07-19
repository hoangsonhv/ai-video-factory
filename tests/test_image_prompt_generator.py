"""Tests for the ImagePromptGenerator service (fake provider, real prompts)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from ai_video_factory.domain.value_objects.chapter import StoryChapter
from ai_video_factory.infrastructure.prompts.service import PromptService
from ai_video_factory.infrastructure.providers.base.models import (
    LLMRequest,
    LLMResponse,
    ProviderHealth,
    TokenUsage,
)
from ai_video_factory.infrastructure.story.errors import ImagePromptParseError
from ai_video_factory.infrastructure.story.image_prompt_generator import ImagePromptGenerator
from ai_video_factory.shared.health import HealthStatus

_REPO_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


def _prompts_json(count: int) -> str:
    return json.dumps(
        {
            "image_prompts": [
                {
                    "scene_number": i,
                    "prompt": f"cinematic visual {i}",
                    "negative_prompt": "blurry",
                    "camera": "wide",
                    "lighting": "golden hour",
                    "character_reference": "young cultivator",
                    "environment": "mountain",
                    "seed": None,
                }
                for i in range(1, count + 1)
            ]
        }
    )


class FakeProvider:
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


def _generator(provider: FakeProvider) -> ImagePromptGenerator:
    return ImagePromptGenerator(provider, PromptService.create(_REPO_PROMPTS))


def _chapter() -> StoryChapter:
    return StoryChapter(title="Tu Tiên", content="Prose narration.", estimated_duration_seconds=60)


def _run(provider: FakeProvider, **kwargs: object):  # type: ignore[no-untyped-def]
    return asyncio.run(_generator(provider).generate(_chapter(), **kwargs))  # type: ignore[arg-type]


def test_generate_returns_prompts_with_injected_fields() -> None:
    provider = FakeProvider([_prompts_json(6)])
    prompts = _run(provider, style="cinematic", aspect_ratio="9:16", count=6)
    assert len(prompts) == 6
    assert all(p.style == "cinematic" and p.aspect_ratio == "9:16" for p in prompts)
    assert prompts[0].camera == "wide"


def test_request_uses_json_mode_and_rendered_prompt() -> None:
    provider = FakeProvider([_prompts_json(3)])
    _run(provider, count=3)
    request = provider.requests[0]
    assert request.json_mode is True
    assert "Tu Tiên" in request.user_prompt
    assert "9:16" in request.user_prompt


def test_retry_once_then_succeeds() -> None:
    provider = FakeProvider(["bad json", _prompts_json(4)])
    prompts = _run(provider, count=4)
    assert len(prompts) == 4
    assert len(provider.requests) == 2


def test_raises_after_retry_exhausted() -> None:
    provider = FakeProvider(["bad", "still bad"])
    with pytest.raises(ImagePromptParseError):
        _run(provider)
    assert len(provider.requests) == 2
