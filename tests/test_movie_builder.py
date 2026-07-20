"""Tests for the MovieBuilder service (fake provider, real prompt template)."""

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
from ai_video_factory.infrastructure.story.errors import MovieBuildError
from ai_video_factory.infrastructure.story.movie_builder import MovieBuilder
from ai_video_factory.shared.health import HealthStatus

_REPO_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


def _movie_json() -> str:
    return json.dumps(
        {
            "title": "The Midnight Delivery",
            "characters": [
                {"id": "shipper", "name": "Nam", "appearance": {"hair": "black"}},
                {"id": "ghost", "name": "Ma", "appearance": {"hair": "white"}},
            ],
            "locations": [{"id": "cemetery", "name": "Cemetery"}],
            "scenes": [
                {
                    "id": 1,
                    "duration": 5,
                    "location": "cemetery",
                    "characters": ["shipper"],
                    "camera": {"shot": "wide", "movement": "drone", "lens": "35mm"},
                    "action": "walk",
                    "emotion": "fear",
                    "image_prompt": "a driver",
                    "video_prompt": "walks",
                },
                {
                    "id": 2,
                    "duration": 5,
                    "location": "cemetery",
                    "characters": ["shipper", "ghost"],
                    "camera": {"shot": "close-up"},
                    "action": "cry",
                    "emotion": "terror",
                    "image_prompt": "a ghost",
                    "video_prompt": "ghost appears",
                },
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


def _chapter() -> StoryChapter:
    return StoryChapter(
        title="Tu Tiên", content="A shipper meets a ghost.", estimated_duration_seconds=60
    )


def _build(provider: FakeProvider, **kwargs: object):  # type: ignore[no-untyped-def]
    builder = MovieBuilder(provider, PromptService.create(_REPO_PROMPTS))
    return asyncio.run(builder.build(_chapter(), **kwargs))  # type: ignore[arg-type]


def test_builds_movie_from_chapter() -> None:
    provider = FakeProvider([_movie_json()])
    movie = _build(provider, style="cinematic", genre="horror")

    assert movie.title == "The Midnight Delivery"
    assert movie.style == "cinematic"  # injected
    assert movie.genre == "horror"  # injected
    assert movie.duration == 60  # from chapter estimated duration
    assert len(movie.characters) == 2
    assert len(movie.scenes) == 2
    # the JSON-mode request was made
    assert provider.requests[0].json_mode is True


def test_extracts_and_names_characters() -> None:
    movie = _build(FakeProvider([_movie_json()]))
    names = {c.name for c in movie.characters}
    assert names == {"Nam", "Ma"}


def test_scenes_reference_characters_and_camera() -> None:
    movie = _build(FakeProvider([_movie_json()]))
    assert movie.scenes[1].characters == ("shipper", "ghost")
    assert movie.scenes[0].camera.movement == "drone"
    assert movie.scenes[1].action == "cry"


def test_retries_once_then_succeeds() -> None:
    provider = FakeProvider(["garbage-not-json", _movie_json()])
    movie = _build(provider)
    assert movie.title == "The Midnight Delivery"
    assert len(provider.requests) == 2  # first attempt failed, retried


def test_raises_after_two_bad_responses() -> None:
    provider = FakeProvider(["nope", "still nope"])
    with pytest.raises(MovieBuildError):
        _build(provider)
    assert len(provider.requests) == 2
