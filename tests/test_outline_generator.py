"""Tests for the OutlineGenerator service (fake provider, real prompt engine)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from ai_video_factory.domain.value_objects.idea import StoryIdea
from ai_video_factory.infrastructure.prompts.service import PromptService
from ai_video_factory.infrastructure.providers.base.models import (
    LLMRequest,
    LLMResponse,
    ProviderHealth,
    TokenUsage,
)
from ai_video_factory.infrastructure.story.errors import OutlineParseError
from ai_video_factory.infrastructure.story.outline_generator import OutlineGenerator
from ai_video_factory.shared.health import HealthStatus

_REPO_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


def _outline_json(chapters: int) -> str:
    return json.dumps(
        {
            "title": "Ma Đạo Tổ Sư",
            "genre": "xianxia",
            "world_setting": "W",
            "cultivation_system": "C",
            "main_character": "M",
            "supporting_characters": ["A", "B"],
            "antagonist": "X",
            "story_arc": "arc",
            "ending": "end",
            "chapter_outlines": [
                {"chapter_number": i, "title": f"C{i}", "summary": "s", "cliffhanger": "!"}
                for i in range(1, chapters + 1)
            ],
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


def _generator(provider: FakeProvider) -> OutlineGenerator:
    return OutlineGenerator(provider, PromptService.create(_REPO_PROMPTS))


def _idea() -> StoryIdea:
    return StoryIdea(title="Tu Tiên", hook="H", summary="S", tags=["a"])


def _run(provider: FakeProvider, chapters: int = 5):  # type: ignore[no-untyped-def]
    return asyncio.run(
        _generator(provider).generate(
            _idea(), target_duration="60s", chapter_count=chapters, language="vi"
        )
    )


def test_generate_returns_outline() -> None:
    provider = FakeProvider([_outline_json(5)])
    outline = _run(provider, 5)
    assert outline.title == "Ma Đạo Tổ Sư"
    assert len(outline.chapter_outlines) == 5


def test_request_uses_json_mode_and_rendered_prompt() -> None:
    provider = FakeProvider([_outline_json(5)])
    _run(provider, 5)
    request = provider.requests[0]
    assert request.json_mode is True
    assert "Tu Tiên" in request.user_prompt
    assert "60s" in request.user_prompt


def test_retry_once_then_succeeds() -> None:
    provider = FakeProvider(["bad json", _outline_json(3)])
    outline = _run(provider, 3)
    assert len(outline.chapter_outlines) == 3
    assert len(provider.requests) == 2


def test_wrong_chapter_count_exhausts_retries() -> None:
    provider = FakeProvider([_outline_json(4), _outline_json(4)])
    with pytest.raises(OutlineParseError):
        _run(provider, 10)
    assert len(provider.requests) == 2
