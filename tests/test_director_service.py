"""Tests for the DirectorService (fake LLM provider — no real API)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from ai_video_factory.domain.value_objects.character_library import (
    CharacterLibrary,
    CharacterProfile,
)
from ai_video_factory.domain.value_objects.director import Shot
from ai_video_factory.domain.value_objects.movie import Camera, Location, Movie, Scene
from ai_video_factory.infrastructure.director.errors import DirectorError
from ai_video_factory.infrastructure.director.service import PARSE_ATTEMPTS, DirectorService
from ai_video_factory.infrastructure.prompts.service import PromptService
from ai_video_factory.infrastructure.providers.base.models import (
    LLMRequest,
    LLMResponse,
    TokenUsage,
)

_SHOT_RAW = {
    "id": 1,
    "duration": 3,
    "camera": "medium shot",
    "camera_motion": "slow push in",
    "lens": "50mm",
    "framing": "centred",
    "subject": "lin_tian",
    "action": "draws a sword",
    "expression": "resolve hardening",
    "environment_motion": "embers drifting",
    "lighting": "hard key",
    "transition": "cut",
    "video_prompt": "he draws the blade",
}


class _FakeProvider:
    """Replays scripted completions and records the prompts it was given."""

    def __init__(self, *contents: str) -> None:
        self._contents = list(contents)
        self.requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self._contents) - 1)
        return LLMResponse(
            content=self._contents[index],
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            provider="fake",
            model="fake-1",
            latency=0.0,
        )


def _movie(scene_count: int = 2) -> Movie:
    return Movie(
        title="Tu Tiên",
        genre="cultivation",
        style="cinematic",
        duration=60,
        locations=(Location(id="cliff", name="Cliff", description="sunrise"),),
        scenes=tuple(
            Scene(
                id=index,
                duration=5,
                location="cliff",
                characters=("lin_tian",),
                camera=Camera(shot="wide shot", movement="drone", lens="35mm"),
                action="walks",
                emotion="resolve",
                dialogue="Có ai không?",
                image_prompt=f"image {index}",
                video_prompt=f"video {index}",
            )
            for index in range(1, scene_count + 1)
        ),
    )


def _library() -> CharacterLibrary:
    return CharacterLibrary(
        characters=(
            CharacterProfile(
                id="lin_tian",
                master_prompt="Lâm Thiên, long black hair",
                negative_prompt="inconsistent face",
                seed=1234,
            ),
        )
    )


def _plan_json(*scene_ids: int) -> str:
    return json.dumps(
        {"scenes": [{"scene_id": scene_id, "shots": [_SHOT_RAW]} for scene_id in scene_ids]}
    )


def _service(*contents: str) -> tuple[DirectorService, _FakeProvider]:
    provider = _FakeProvider(*contents)
    prompts = PromptService.create(Path("prompts"))  # the real shipped template
    return DirectorService(provider, prompts), provider  # type: ignore[arg-type]


# --- direction -------------------------------------------------------------


def test_direct_attaches_a_shot_plan_to_every_scene() -> None:
    service, _ = _service(_plan_json(1, 2))

    directed, _ = asyncio.run(service.direct(_movie(), _library()))

    assert len(directed.scenes) == 2
    assert directed.scenes[0].shots[0].camera == "medium shot"
    assert directed.scenes[1].shots[0].environment_motion == "embers drifting"


def test_direct_composes_a_prompt_per_scene() -> None:
    service, _ = _service(_plan_json(1, 2))

    directed, _ = asyncio.run(service.direct(_movie(), _library()))

    for scene in directed.scenes:
        assert scene.is_planned
        assert "Lâm Thiên" in scene.shots[0].video_prompt
        assert "temporally coherent" in scene.shots[0].video_prompt


def test_direct_preserves_every_original_scene_field() -> None:
    movie = _movie()
    service, _ = _service(_plan_json(1, 2))

    directed, _ = asyncio.run(service.direct(movie, _library()))

    for original, result in zip(movie.scenes, directed.scenes, strict=True):
        assert result.id == original.id
        assert result.duration == original.duration
        assert result.camera == original.camera
        assert result.dialogue == original.dialogue
        assert result.image_prompt == original.image_prompt
        assert result.video_prompt == original.video_prompt  # never rewritten


def test_direct_preserves_the_movie_header() -> None:
    service, _ = _service(_plan_json(1, 2))

    directed, _ = asyncio.run(service.direct(_movie(), _library()))

    assert directed.title == "Tu Tiên"
    assert directed.genre == "cultivation"
    assert directed.style == "cinematic"
    assert directed.duration == 60
    assert directed.locations == _movie().locations


def test_a_scene_the_answer_omits_is_left_unplanned() -> None:
    """With one bulk answer, a missing scene id means that scene has no plan."""
    service, _ = _service(_plan_json(1))  # scene 2 omitted

    directed, report = asyncio.run(service.direct(_movie(), _library()))

    assert report.directed == 1
    assert report.failed_scene_ids == (2,)
    assert directed.scenes[1].shots == ()


def test_a_sparse_shot_keeps_its_blanks_rather_than_inventing_filler() -> None:
    """Only what the model actually said is kept; gaps stay gaps."""
    sparse = '{"scenes":[{"scene_id":1,"shots":[{"duration":3,"camera":"close-up"}]}]}'
    service, _ = _service(sparse)

    directed, _ = asyncio.run(service.direct(_movie(scene_count=1), _library()))

    shot = directed.scenes[0].shots[0]
    assert shot.camera == "close-up"
    assert shot.lens == ""
    assert shot.environment_motion == ""
    assert shot.video_prompt  # still composed, from what is known


def test_direct_works_without_a_character_library() -> None:
    service, _ = _service(_plan_json(1, 2))

    directed, _ = asyncio.run(service.direct(_movie(), None))

    assert directed.scenes[0].is_planned
    assert "Lâm Thiên" not in directed.scenes[0].shots[0].video_prompt


def test_direct_is_deterministic_for_a_given_plan() -> None:
    service, _ = _service(_plan_json(1, 2))
    movie, library = _movie(), _library()
    plan = {1: [Shot.model_validate(_SHOT_RAW)], 2: [Shot.model_validate(_SHOT_RAW)]}

    assert service.apply(movie, plan, library) == service.apply(movie, plan, library)


# --- request construction --------------------------------------------------


def test_each_json_mode_request_covers_one_scene() -> None:
    service, provider = _service(_plan_json(1, 2))

    asyncio.run(service.direct(_movie(), _library()))

    assert len(provider.requests) == 2  # one call per scene
    request = provider.requests[0]
    assert request.json_mode
    assert request.metadata["stage"] == "director"
    assert request.metadata["scene_id"] == "1"
    assert "id 1 " in request.user_prompt
    assert "id 2 " not in request.user_prompt


def test_the_prompt_forbids_re_describing_characters() -> None:
    """Re-describing a character is what breaks Sprint 019's consistency."""
    service, provider = _service(_plan_json(1))

    asyncio.run(service.direct(_movie(scene_count=1), _library()))

    assert "identity is fixed elsewhere" in provider.requests[0].user_prompt


# --- failure handling ------------------------------------------------------


def test_unparseable_output_re_asks_that_scene_then_fails_it() -> None:
    """The scene is abandoned, but the run is not."""
    service, provider = _service("not json")

    _, report = asyncio.run(service.direct(_movie(), _library()))

    assert len(provider.requests) == PARSE_ATTEMPTS * 2  # each scene tries alone
    assert report.failed == 2


def test_direct_rejects_a_movie_without_scenes() -> None:
    service, provider = _service(_plan_json(1))

    with pytest.raises(DirectorError, match="no scenes to direct"):
        asyncio.run(service.direct(_movie(scene_count=0), _library()))

    assert provider.requests == []  # fails before spending a call
