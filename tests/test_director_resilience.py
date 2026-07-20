"""Tests for director resilience: one request per scene, retry, partial, resume.

The movie is planned **incrementally** - one request per scene, appended and
saved as it lands. A scene that fails never stops the run.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from ai_video_factory.domain.value_objects.character_library import (
    CharacterLibrary,
    CharacterProfile,
)
from ai_video_factory.domain.value_objects.director import DirectedMovie
from ai_video_factory.domain.value_objects.movie import Camera, Location, Movie, Scene
from ai_video_factory.infrastructure.director.errors import DirectorError
from ai_video_factory.infrastructure.director.service import (
    BASE_DELAY,
    JITTER,
    MAX_DELAY,
    MAX_RETRIES,
    MAX_TOKENS,
    PARSE_ATTEMPTS,
    DirectorService,
)
from ai_video_factory.infrastructure.prompts.service import PromptService
from ai_video_factory.infrastructure.providers.base.errors import (
    AuthenticationError,
    InvalidResponseError,
    ProviderUnavailableError,
    RateLimitError,
)
from ai_video_factory.infrastructure.providers.base.errors import (
    TimeoutError as ProviderTimeoutError,
)
from ai_video_factory.infrastructure.providers.base.models import (
    LLMRequest,
    LLMResponse,
    TokenUsage,
)

_SHOT = {
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


def _plan(*scene_ids: int, shots: int = 3) -> str:
    """One answer covering every listed scene - the shape the director expects."""
    return json.dumps(
        {
            "scenes": [
                {"scene_id": sid, "shots": [{**_SHOT, "id": n + 1} for n in range(shots)]}
                for sid in scene_ids
            ]
        }
    )


class _ScriptedProvider:
    """Replays outcomes in call order: an Exception raises, a str is returned."""

    def __init__(self, *outcomes: object) -> None:
        self._outcomes = list(outcomes) or [_plan(1, 2, 3)]
        self.requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self._outcomes) - 1)
        outcome = self._outcomes[index]
        if isinstance(outcome, Exception):
            raise outcome
        return LLMResponse(
            content=str(outcome),
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            provider="fake",
            model="fake-1",
            latency=0.0,
        )

    @property
    def calls(self) -> int:
        return len(self.requests)


def _movie(scene_count: int = 3) -> Movie:
    return Movie(
        title="Tu Tiên",
        style="cinematic",
        duration=60,
        locations=(Location(id="cliff", name="Cliff", description="sunrise"),),
        scenes=tuple(
            Scene(
                id=index,
                duration=9,
                location="cliff",
                characters=("lin_tian",),
                camera=Camera(shot="wide shot", movement="drone", lens="35mm"),
                action="walks",
                emotion="resolve",
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
                master_prompt="Lâm Thiên",
                negative_prompt="blurry",
                voice_profile="young male, calm",
            ),
        )
    )


def _service(*outcomes: object) -> tuple[DirectorService, _ScriptedProvider]:
    provider = _ScriptedProvider(*outcomes)
    delays: list[float] = []

    async def _sleep(seconds: float) -> None:
        delays.append(seconds)

    service = DirectorService(
        provider,  # type: ignore[arg-type]
        PromptService.create(Path("prompts")),
        sleep=_sleep,
    )
    service.delays = delays  # type: ignore[attr-defined]
    return service, provider


# --- one request per scene -------------------------------------------------


def test_a_movie_costs_one_request_per_scene() -> None:
    service, provider = _service(_plan(1, 2, 3))

    directed, report = asyncio.run(service.direct(_movie(), _library()))

    assert provider.calls == 3
    assert report.directed == 3
    assert all(scene.is_planned for scene in directed.scenes)


def test_a_ten_scene_movie_costs_ten_requests() -> None:
    service, provider = _service(_plan(*range(1, 11)))

    _, report = asyncio.run(service.direct(_movie(scene_count=10), _library()))

    assert provider.calls == 10
    assert report.directed == 10


def test_each_request_carries_exactly_one_scene() -> None:
    service, provider = _service(_plan(1, 2, 3))

    asyncio.run(service.direct(_movie(), _library()))

    for index, scene_id in enumerate((1, 2, 3)):
        prompt = provider.requests[index].user_prompt
        assert f"id {scene_id} " in prompt
        for other in {1, 2, 3} - {scene_id}:
            assert f"id {other} " not in prompt
        assert provider.requests[index].metadata["scene_id"] == str(scene_id)


def test_the_answer_stays_inside_its_token_budget() -> None:
    """A whole-movie answer did not fit; one scene's must."""
    service, provider = _service(_plan(1, 2, 3))

    asyncio.run(service.direct(_movie(), _library()))

    assert provider.requests[0].max_tokens == MAX_TOKENS
    assert MAX_TOKENS <= 4000


def test_the_request_carries_the_character_library_and_locations() -> None:
    service, provider = _service(_plan(1, 2, 3))

    asyncio.run(service.direct(_movie(), _library()))

    prompt = provider.requests[0].user_prompt
    assert "lin_tian" in prompt  # cast, referenced by id
    assert "cliff" in prompt  # location id
    assert "sunrise" in prompt  # location description


def test_the_request_never_leaks_a_character_appearance() -> None:
    """Re-describing a character is what breaks the consistency guarantee."""
    service, provider = _service(_plan(1, 2, 3))

    asyncio.run(service.direct(_movie(), _library()))

    prompt = provider.requests[0].user_prompt
    assert "Lâm Thiên" not in prompt  # the master prompt stays out
    assert "identity is fixed elsewhere" in prompt


def test_the_request_uses_json_mode() -> None:
    service, provider = _service(_plan(1, 2, 3))

    asyncio.run(service.direct(_movie(), _library()))

    assert provider.requests[0].json_mode
    assert provider.requests[0].metadata["stage"] == "director"


# --- retry: transient transport failures -----------------------------------


@pytest.mark.parametrize(
    "error",
    [
        ProviderUnavailableError("502 bad gateway"),
        ProviderUnavailableError("503 service unavailable"),
        ProviderUnavailableError("504 gateway timeout"),
        ProviderTimeoutError("connection timeout"),
        ProviderTimeoutError("read timeout"),
        RateLimitError("429"),
    ],
)
def test_every_transient_failure_retries_that_scene(error: Exception) -> None:
    service, provider = _service(error, _plan(1, 2, 3))

    _, report = asyncio.run(service.direct(_movie(), _library()))

    assert provider.calls == 4  # scene 1 re-asked, then scenes 2 and 3
    assert report.directed == 3
    assert report.retries == 1


def test_transient_retries_stop_at_the_maximum_per_scene() -> None:
    service, provider = _service(ProviderUnavailableError("503"))

    _, report = asyncio.run(service.direct(_movie(), _library()))

    # Every scene exhausts its own retries, and the run still finishes.
    assert provider.calls == (MAX_RETRIES + 1) * 3
    assert report.failed == 3
    assert report.failed_scene_ids == (1, 2, 3)


def test_the_backoff_is_exponential_with_jitter() -> None:
    service, _ = _service(ProviderUnavailableError("503"))

    asyncio.run(service.direct(_movie(scene_count=1), _library()))

    delays = service.delays  # type: ignore[attr-defined]
    assert len(delays) == MAX_RETRIES
    for index, delay in enumerate(delays):
        nominal = min(MAX_DELAY, BASE_DELAY * (2**index))  # 1, 2, 4, 8, 16
        assert nominal * (1 - JITTER) <= delay <= nominal * (1 + JITTER)


@pytest.mark.parametrize("error", [AuthenticationError("bad key"), InvalidResponseError("junk")])
def test_a_terminal_error_is_not_retried(error: Exception) -> None:
    service, provider = _service(error)

    _, report = asyncio.run(service.direct(_movie(scene_count=1), _library()))

    assert provider.calls == 1
    assert report.failed == 1


# --- retry: invalid JSON ---------------------------------------------------


def test_invalid_json_re_asks_that_scene() -> None:
    service, provider = _service("not json at all", _plan(1, 2, 3))

    directed, report = asyncio.run(service.direct(_movie(), _library()))

    assert provider.calls == 4  # scene 1 re-asked, then scenes 2 and 3
    assert report.retries == 1
    assert all(scene.is_planned for scene in directed.scenes)


def test_invalid_json_gives_up_after_the_configured_attempts() -> None:
    service, provider = _service("not json at all")

    _, report = asyncio.run(service.direct(_movie(scene_count=1), _library()))

    assert provider.calls == PARSE_ATTEMPTS
    assert report.failed == 1


def test_an_empty_scenes_array_counts_as_unparseable() -> None:
    service, provider = _service('{"scenes":[]}')

    _, report = asyncio.run(service.direct(_movie(scene_count=1), _library()))

    assert provider.calls == PARSE_ATTEMPTS
    assert report.failed == 1


def test_markdown_fences_are_tolerated_without_a_retry() -> None:
    service, provider = _service(f"```json\n{_plan(1, 2, 3)}\n```")

    _, report = asyncio.run(service.direct(_movie(), _library()))

    assert provider.calls == 3
    assert report.retries == 0


# --- mapping the answer back -----------------------------------------------


def test_the_plan_is_mapped_onto_the_matching_scene_ids() -> None:
    answer = json.dumps(
        {
            "scenes": [
                {"scene_id": 1, "shots": [{**_SHOT, "camera": "close-up"}]},
                {"scene_id": 2, "shots": [{**_SHOT, "camera": "wide shot"}]},
                {"scene_id": 3, "shots": [{**_SHOT, "camera": "insert"}]},
            ]
        }
    )
    service, _ = _service(answer)

    directed, _ = asyncio.run(service.direct(_movie(), _library()))

    assert [scene.shots[0].camera for scene in directed.scenes] == [
        "close-up",
        "wide shot",
        "insert",
    ]


def test_every_scene_is_broken_into_multiple_shots() -> None:
    service, _ = _service(_plan(1, 2, 3, shots=4))

    directed, _ = asyncio.run(service.direct(_movie(), _library()))

    assert [len(scene.shots) for scene in directed.scenes] == [4, 4, 4]
    assert directed.shot_count == 12
    assert [shot.id for shot in directed.scenes[0].shots] == [1, 2, 3, 4]


def test_each_shot_gets_its_own_composed_prompt() -> None:
    service, _ = _service(_plan(1, 2, 3))

    directed, _ = asyncio.run(service.direct(_movie(), _library()))

    for shot in directed.scenes[0].shots:
        assert shot.video_prompt
        assert "Lâm Thiên" in shot.video_prompt  # identity from the library
        assert "temporally coherent" in shot.video_prompt


def test_original_scene_fields_survive_the_mapping() -> None:
    movie = _movie()
    service, _ = _service(_plan(1, 2, 3))

    directed, _ = asyncio.run(service.direct(movie, _library()))

    for original, result in zip(movie.scenes, directed.scenes, strict=True):
        assert result.id == original.id
        assert result.camera == original.camera
        assert result.video_prompt == original.video_prompt  # never rewritten


def test_a_scene_the_answer_omitted_is_left_unplanned() -> None:
    service, _ = _service(_plan(1, 3))  # scene 2 missing

    directed, report = asyncio.run(service.direct(_movie(), _library()))

    assert report.directed == 2
    assert report.failed == 1
    assert report.failed_scene_ids == (2,)
    assert directed.scenes[1].shots == ()  # the resume marker
    assert directed.scenes[1].video_prompt == "video 2"  # content intact


def test_a_failed_scene_does_not_stop_the_run() -> None:
    """The whole point of planning incrementally."""
    service, provider = _service(_plan(1, 3))

    _, report = asyncio.run(service.direct(_movie(), _library()))

    assert provider.calls == 3  # every scene still got its turn
    assert report.directed == 2
    assert report.failed == 1


# --- resume ----------------------------------------------------------------


def _partial() -> DirectedMovie:
    service, _ = _service(_plan(1, 3))
    directed, _ = asyncio.run(service.direct(_movie(), _library()))
    return directed


def test_resume_asks_only_about_the_unplanned_scenes() -> None:
    previous = _partial()
    service, provider = _service(_plan(2))

    directed, report = asyncio.run(service.direct(_movie(), _library(), resume_from=previous))

    assert provider.calls == 1  # only scene 2 is still missing
    prompt = provider.requests[0].user_prompt
    assert "id 2 " in prompt
    assert "id 1 " not in prompt  # already done, not re-sent
    assert report.directed == 1
    assert report.skipped == 2
    assert report.is_complete
    assert all(scene.is_planned for scene in directed.scenes)


def test_resume_preserves_the_already_directed_scenes_verbatim() -> None:
    previous = _partial()
    service, _ = _service(_plan(2))

    directed, _ = asyncio.run(service.direct(_movie(), _library(), resume_from=previous))

    assert directed.scenes[0] == previous.scenes[0]
    assert directed.scenes[2] == previous.scenes[2]


def test_resume_from_a_complete_run_makes_no_request_at_all() -> None:
    service, _ = _service(_plan(1, 2, 3))
    complete, _ = asyncio.run(service.direct(_movie(), _library()))
    resumed, provider = _service(_plan(1, 2, 3))

    _, report = asyncio.run(resumed.direct(_movie(), _library(), resume_from=complete))

    assert provider.calls == 0
    assert report.skipped == 3
    assert report.is_complete


def test_resume_without_a_previous_run_directs_everything() -> None:
    service, provider = _service(_plan(1, 2, 3))

    _, report = asyncio.run(service.direct(_movie(), _library(), resume_from=None))

    assert provider.calls == 3
    assert report.directed == 3
    assert report.skipped == 0


# --- guards ----------------------------------------------------------------


def test_a_movie_without_scenes_is_rejected_before_any_call() -> None:
    service, provider = _service(_plan(1))

    with pytest.raises(DirectorError, match="no scenes to direct"):
        asyncio.run(service.direct(_movie(scene_count=0), _library()))

    assert provider.calls == 0


def test_directing_works_without_a_character_library() -> None:
    service, provider = _service(_plan(1, 2, 3))

    directed, report = asyncio.run(service.direct(_movie(), None))

    assert provider.calls == 3
    assert report.directed == 3
    assert "Lâm Thiên" not in directed.scenes[0].shots[0].video_prompt


def test_an_injected_scene_prompt_does_not_leak_appearance_back() -> None:
    """movie_consistent.json prepends each master prompt to every scene prompt.

    Passing that through would restate the appearance the director is told not
    to describe, so it is stripped before the request is built.
    """
    injected = (
        "Lâm Thiên, long black hair, consistent character design | "
        "stands on the cliff at sunrise | negative: blurry, inconsistent face"
    )
    movie = _movie(scene_count=1)
    scene = movie.scenes[0].model_copy(update={"video_prompt": injected})
    movie = movie.model_copy(update={"scenes": (scene,)})
    library = CharacterLibrary(
        characters=(
            CharacterProfile(
                id="lin_tian",
                master_prompt="Lâm Thiên, long black hair, consistent character design",
                negative_prompt="blurry, inconsistent face",
            ),
        )
    )
    service, provider = _service(_plan(1))

    asyncio.run(service.direct(movie, library))

    prompt = provider.requests[0].user_prompt
    assert "long black hair" not in prompt  # the appearance is gone
    assert "stands on the cliff at sunrise" in prompt  # the beat survives
    assert "negative:" not in prompt.split("## Field")[0]
