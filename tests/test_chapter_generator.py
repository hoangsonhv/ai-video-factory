"""Tests for the ChapterGenerator service (fake provider, real prompt engine)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from ai_video_factory.domain.value_objects.outline import StoryOutline
from ai_video_factory.infrastructure.prompts.service import PromptService
from ai_video_factory.infrastructure.providers.base.models import (
    LLMRequest,
    LLMResponse,
    ProviderHealth,
    TokenUsage,
)
from ai_video_factory.infrastructure.story.chapter_generator import ChapterGenerator
from ai_video_factory.infrastructure.story.errors import ChapterParseError
from ai_video_factory.shared.health import HealthStatus

_REPO_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
_CHAPTER = json.dumps({"title": "Tu Tiên Ký", "content": " ".join(["từ"] * 150)})


def _outline() -> StoryOutline:
    return StoryOutline.model_validate(
        {
            "title": "Tu Tiên Ký",
            "genre": "xianxia",
            "world_setting": "W",
            "cultivation_system": "C",
            "main_character": "M",
            "supporting_characters": ["A", "B"],
            "antagonist": "X",
            "story_arc": "arc",
            "ending": "end",
            "chapter_outlines": [
                {"chapter_number": 1, "title": "C1", "summary": "s", "cliffhanger": "!"},
                {"chapter_number": 2, "title": "C2", "summary": "s", "cliffhanger": "!"},
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


def _generator(provider: FakeProvider):  # type: ignore[no-untyped-def]
    return ChapterGenerator(provider, PromptService.create(_REPO_PROMPTS))


def _run(provider: FakeProvider):  # type: ignore[no-untyped-def]
    return asyncio.run(_generator(provider).generate(_outline(), language="vi"))


def test_generate_returns_chapter_with_duration() -> None:
    provider = FakeProvider([_CHAPTER])
    chapter = _run(provider)
    assert chapter.title == "Tu Tiên Ký"
    assert chapter.estimated_duration_seconds == 60  # 150 words at 150 wpm


def test_request_uses_json_mode_and_rendered_prompt() -> None:
    provider = FakeProvider([_CHAPTER])
    _run(provider)
    request = provider.requests[0]
    assert request.json_mode is True
    assert "Tu Tiên Ký" in request.user_prompt
    assert "C1" in request.user_prompt  # chapter outline was included


def test_retry_once_then_succeeds() -> None:
    provider = FakeProvider(["bad json", _CHAPTER])
    chapter = _run(provider)
    assert chapter.estimated_duration_seconds == 60
    assert len(provider.requests) == 2


def test_raises_after_retry_exhausted() -> None:
    provider = FakeProvider(["bad", "still bad"])
    with pytest.raises(ChapterParseError):
        _run(provider)
    assert len(provider.requests) == 2
