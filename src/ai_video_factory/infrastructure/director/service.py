"""AI Director (infrastructure service).

Breaks a movie's scenes into **shots** — the unit an AI video model renders —
and composes each shot's prompt. It reads the character library so identities
stay fixed, and it **adds** to the movie rather than rewriting it: every
original scene field is preserved.

**One provider request plans one scene.** The movie is planned incrementally:
each scene is asked for on its own, appended as soon as it lands, and handed to
the caller so the partial result can be saved before the next request goes out.
A scene that fails is left unplanned and the run **continues** — one bad scene
never costs the nine that already succeeded, and ``--resume`` re-asks only for
what is missing.

This costs one request per scene rather than one per movie. That is the
deliberate trade: a whole-movie answer has to fit every scene's shots into one
completion, which is what pushed the response past its token budget. A per-scene
request needs a small answer (:data:`MAX_TOKENS`) and carries a hard
:data:`SCENE_TIMEOUT` deadline, so a stalled request loses one scene instead of
the movie.

Retries apply per scene: transient transport failures (429/5xx, connection and
read timeouts) back off exponentially with jitter, and an unparseable answer
re-asks that scene.

It calls no video provider, touches no image generation, and leaves the Movie
Builder and Character Library untouched.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence

from ai_video_factory.domain.value_objects.character_library import (
    CharacterLibrary,
    CharacterProfile,
)
from ai_video_factory.domain.value_objects.director import (
    MAX_SHOT_SECONDS,
    MIN_SHOT_SECONDS,
    DirectedMovie,
    DirectedScene,
    Shot,
)
from ai_video_factory.domain.value_objects.movie import Location, Movie, Scene
from ai_video_factory.infrastructure.config.settings import Settings
from ai_video_factory.infrastructure.director.errors import DirectorError
from ai_video_factory.infrastructure.director.prompt_builder import build_shot_prompt
from ai_video_factory.infrastructure.director.report import DirectionReport
from ai_video_factory.infrastructure.director.shot_parser import parse_shot_plan
from ai_video_factory.infrastructure.director.shot_planner import target_shot_count
from ai_video_factory.infrastructure.prompts.service import PromptService
from ai_video_factory.infrastructure.providers.base.errors import AIProviderError
from ai_video_factory.infrastructure.providers.base.models import LLMRequest
from ai_video_factory.infrastructure.providers.base.provider import LLMProvider
from ai_video_factory.infrastructure.providers.base.retry import RetryPolicy
from ai_video_factory.infrastructure.providers.factory.provider_factory import ProviderFactory

_logger = logging.getLogger(__name__)

_PROMPT_NAME = "director/shot_plan"
_TEMPERATURE = 0.7

MAX_TOKENS = 4000
"""One scene's shots need a small answer; a whole movie's did not fit."""

SCENE_TIMEOUT = 60.0
"""Hard deadline per scene, enforced here rather than in any provider.

``LLMRequest`` carries no timeout and this stage may not change a provider, so
the director owns its own deadline. A scene that overruns is failed and the run
continues.
"""

MAX_RETRIES = 5
BASE_DELAY = 1.0
MAX_DELAY = 16.0
JITTER = 0.2
"""Transport back-off per scene: 1s, 2s, 4s, 8s, 16s ±20%."""

PARSE_ATTEMPTS = 3
"""Total tries when the model answers with something unparseable."""

ProgressCallback = Callable[[int, str], None]
"""Invoked with ``(scenes_remaining, phase)`` as the run progresses."""

SceneSaveCallback = Callable[[DirectedMovie], None]
"""Invoked with the movie so far, after **every** scene is planned."""

PHASE_PLANNING = "planning"
PHASE_RETRYING = "retrying"
PHASE_MAPPING = "mapping"
PHASE_FAILED = "failed"
PHASE_DONE = "done"


class DirectorService:
    """Breaks a :class:`Movie` into shots using one provider request."""

    def __init__(
        self,
        provider: LLMProvider,
        prompts: PromptService,
        *,
        model: str | None = None,
        on_progress: ProgressCallback | None = None,
        on_scene_saved: SceneSaveCallback | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._provider = provider
        self._prompts = prompts
        self._model = model
        self._on_progress = on_progress
        self._on_scene_saved = on_scene_saved
        self._sleep = sleep
        self._retries = 0

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        on_progress: ProgressCallback | None = None,
        on_scene_saved: SceneSaveCallback | None = None,
    ) -> DirectorService:
        """Build the director from configuration (provider + prompt root).

        The director may run on its **own** provider and model
        (``AIVF_DIRECTOR_PROVIDER``); unset, it shares the story pipeline's.

        ``on_scene_saved`` is invoked with the movie so far after every scene,
        so the caller can persist a partial result without this service owning
        a file path.
        """
        provider = ProviderFactory.create_director(settings)
        prompts = PromptService.create(settings.prompts.root)
        return cls(
            provider,
            prompts,
            model=ProviderFactory.director_model(settings),
            on_progress=on_progress,
            on_scene_saved=on_scene_saved,
        )

    async def direct(
        self,
        movie: Movie,
        library: CharacterLibrary | None = None,
        *,
        resume_from: DirectedMovie | None = None,
    ) -> tuple[DirectedMovie, DirectionReport]:
        """Plan the movie one scene at a time, saving after each.

        Each scene is asked for on its own request, appended immediately, and
        the movie so far is handed to ``on_scene_saved`` before the next
        request goes out — so a run interrupted at any point leaves usable
        work on disk.

        A scene that exhausts its retries, overruns :data:`SCENE_TIMEOUT` or
        answers unparseably is **left unplanned and the run continues**;
        ``resume_from`` reuses everything that already carries shots.

        Raises:
            DirectorError: If the movie declares no scenes.
        """
        if not movie.scenes:
            raise DirectorError("movie declares no scenes to direct")

        self._retries = 0
        completed = self._completed(resume_from)
        pending = [scene for scene in movie.scenes if scene.id not in completed]
        profiles = self._profiles(library)
        locations = self._locations(movie)

        planned: dict[int, DirectedScene] = {}
        failed: list[int] = []
        remaining = len(pending)

        for scene in pending:
            self._report(remaining, PHASE_PLANNING)
            shots = await self._plan_scene(movie, scene, library)
            if shots:
                planned[scene.id] = self._compose(movie, scene, shots, profiles, locations)
            else:
                # Leave it unplanned rather than pass filler off as a shot plan
                # — emptiness is exactly what --resume looks for.
                failed.append(scene.id)
                self._report(remaining, PHASE_FAILED)
            remaining -= 1
            # Save after every scene, successful or not, so the work already
            # done survives whatever happens to the next request.
            self._save(self._merge(movie, completed, planned))

        self._report(0, PHASE_MAPPING)
        merged = self._merge(movie, completed, planned)
        self._report(0, PHASE_DONE)

        report = DirectionReport(
            directed=len(planned),
            failed=len(failed),
            retries=self._retries,
            skipped=len(completed),
            failed_scene_ids=tuple(failed),
        )
        return merged, report

    def apply(
        self,
        movie: Movie,
        plan: dict[int, list[Shot]],
        library: CharacterLibrary | None = None,
    ) -> DirectedMovie:
        """Attach ``plan`` to ``movie`` and compose every shot's prompt.

        Pure and deterministic: the same movie and plan always give the same
        directed movie. A scene missing from ``plan`` is left without shots.
        """
        profiles = self._profiles(library)
        locations = self._locations(movie)
        directed = tuple(
            self._compose(movie, scene, plan.get(scene.id, []), profiles, locations)
            for scene in movie.scenes
        )
        return self._assemble(movie, directed)

    # --- one request per scene ----------------------------------------------

    async def _plan_scene(
        self, movie: Movie, scene: Scene, library: CharacterLibrary | None
    ) -> list[Shot]:
        """Ask for the shots of one scene, returning ``[]` if it cannot be had.

        Transient transport failures back off with jitter; an unparseable
        answer re-asks this scene up to :data:`PARSE_ATTEMPTS` times; the whole
        attempt is bounded by :data:`SCENE_TIMEOUT`. Every failure mode returns
        empty rather than raising, because one scene must never stop the run.
        """
        request = self._build_request(movie, scene, library)
        durations = {scene.id: scene.duration}
        retry = RetryPolicy(
            max_retries=MAX_RETRIES,
            base_delay=BASE_DELAY,
            max_delay=MAX_DELAY,
            jitter=JITTER,
            sleep=self._sleep,
            on_retry=self._count_retry(scene.id),
        )
        for attempt in range(1, PARSE_ATTEMPTS + 1):
            try:
                response = await self._with_deadline(
                    retry.run(lambda: self._provider.generate(request))
                )
            except TimeoutError:
                _logger.warning(
                    "director scene %d exceeded its %.0fs deadline", scene.id, SCENE_TIMEOUT
                )
                return []
            except AIProviderError as exc:
                _logger.warning("director scene %d failed: %s", scene.id, exc)
                return []
            try:
                return parse_shot_plan(response.content, durations).get(scene.id, [])
            except DirectorError as exc:
                if attempt < PARSE_ATTEMPTS:
                    self._retries += 1
                    self._report(scene.id, PHASE_RETRYING)
                    _logger.warning(
                        "director scene %d unparseable (attempt %d/%d): %s",
                        scene.id,
                        attempt,
                        PARSE_ATTEMPTS,
                        exc,
                    )
                else:
                    _logger.warning("director scene %d gave no usable plan: %s", scene.id, exc)
        return []

    @staticmethod
    async def _with_deadline[T](awaitable: Awaitable[T]) -> T:
        """Bound one scene's request, including its retries, at the deadline."""
        return await asyncio.wait_for(awaitable, timeout=SCENE_TIMEOUT)

    def _count_retry(self, scene_id: int) -> Callable[[int, float, AIProviderError], None]:
        def _hook(attempt: int, delay: float, exc: AIProviderError) -> None:
            self._retries += 1
            self._report(scene_id, PHASE_RETRYING)
            _logger.warning(
                "director scene %d attempt %d failed (%s); retrying in %.1fs",
                scene_id,
                attempt,
                exc,
                delay,
            )

        return _hook

    def _build_request(
        self, movie: Movie, scene: Scene, library: CharacterLibrary | None
    ) -> LLMRequest:
        """Build the request for exactly one scene.

        The batch template is reused with a single scene: it already renders one
        line per scene and asks for a ``{"scenes": [...]}`` answer, so a
        one-scene list needs no new template and no change to the parser.
        """
        prompt = self._prompts.render(
            _PROMPT_NAME,
            {
                "title": movie.title,
                "genre": movie.genre,
                "style": movie.style,
                "scene_count": 1,
                "scenes": self._describe_scenes((scene,), self._profiles(library)),
                "characters": self._describe_characters(library),
                "locations": self._describe_locations(movie),
                "min_shot_seconds": MIN_SHOT_SECONDS,
                "max_shot_seconds": MAX_SHOT_SECONDS,
            },
        )
        return LLMRequest(
            user_prompt=prompt,
            model=self._model,
            json_mode=True,
            temperature=_TEMPERATURE,
            max_tokens=MAX_TOKENS,
            metadata={"stage": "director", "scene_id": str(scene.id)},
        )

    @classmethod
    def _describe_scenes(
        cls, scenes: Sequence[Scene], profiles: dict[str, CharacterProfile]
    ) -> str:
        return "\n".join(
            f"- id {scene.id} ({scene.duration}s) | "
            f"produce {target_shot_count(scene.duration)} shots | characters: "
            f"{', '.join(scene.characters) or 'none'} | location: {scene.location or 'none'} | "
            f"camera hints: {scene.camera.shot} {scene.camera.movement} {scene.camera.lens} | "
            f"action: {scene.action} | emotion: {scene.emotion} | "
            f"{cls._beat(scene, profiles)}"
            for scene in scenes
        )

    @staticmethod
    def _beat(scene: Scene, profiles: dict[str, CharacterProfile]) -> str:
        """The scene's own description, with any injected identity stripped out.

        ``movie_consistent.json`` has each character's master prompt prepended
        to every scene prompt (ADR-026). Passing that through would restate the
        appearance the director is told not to describe — bloating the request
        and inviting the model to echo it back into shot fields. Only the beat
        the director actually needs is sent.
        """
        text = scene.video_prompt or scene.image_prompt
        for profile in profiles.values():
            if profile.master_prompt:
                text = text.replace(profile.master_prompt, "")
        # Drop the trailing negative-prompt tail the injector appends.
        head, marker, _ = text.partition("negative:")
        cleaned = (head if marker else text).strip(" |,")
        return " ".join(cleaned.split()) or scene.action

    @staticmethod
    def _describe_characters(library: CharacterLibrary | None) -> str:
        """The cast, by id — appearance is deliberately omitted.

        The director must reference characters, never re-describe them; their
        look is fixed by the character library (ADR-026).
        """
        if library is None or not library.characters:
            return "(none)"
        return "\n".join(
            f"- {profile.id}: {profile.voice_profile or 'no voice note'}"
            for profile in library.characters
        )

    @staticmethod
    def _describe_locations(movie: Movie) -> str:
        if not movie.locations:
            return "(none)"
        return "\n".join(
            f"- {location.id}: {location.name} — {location.description}"
            for location in movie.locations
        )

    # --- mapping the answer back onto the movie -----------------------------

    def _merge(
        self,
        movie: Movie,
        completed: dict[int, DirectedScene],
        planned: dict[int, DirectedScene],
    ) -> DirectedMovie:
        """Assemble every scene back into one movie, in the movie's own order.

        Resumed scenes, scenes planned in this run and scenes not yet reached
        all appear; a scene with no plan is carried through without shots, which
        is what ``--resume`` looks for.
        """
        scenes = tuple(
            planned.get(scene.id)
            or completed.get(scene.id)
            or DirectedScene.model_validate(scene.model_dump())
            for scene in movie.scenes
        )
        return self._assemble(movie, scenes)

    def _save(self, movie: DirectedMovie) -> None:
        """Hand the movie so far to the caller, if there is progress to save.

        A movie in which nothing has been planned is deliberately **not**
        handed over: writing it would leave a partial file holding no shots,
        which ``--resume`` would then treat as work already done.
        """
        if self._on_scene_saved is None:
            return
        if not any(scene.is_planned for scene in movie.scenes):
            return
        self._on_scene_saved(movie)

    def _compose(
        self,
        movie: Movie,
        scene: Scene,
        shots: Sequence[Shot],
        profiles: dict[str, CharacterProfile],
        locations: dict[str, Location],
    ) -> DirectedScene:
        """Attach ``shots`` to ``scene``, composing each one's final prompt."""
        base = DirectedScene.model_validate(scene.model_dump())
        composed = tuple(
            shot.model_copy(
                update={"video_prompt": build_shot_prompt(movie, base, shot, profiles, locations)}
            )
            for shot in shots
        )
        return base.model_copy(update={"shots": composed})

    @staticmethod
    def _assemble(movie: Movie, scenes: tuple[DirectedScene, ...]) -> DirectedMovie:
        return DirectedMovie(**movie.model_dump(exclude={"scenes"}), scenes=scenes)

    @staticmethod
    def _completed(resume_from: DirectedMovie | None) -> dict[int, DirectedScene]:
        """Scenes from a previous run that already carry shots."""
        if resume_from is None:
            return {}
        return {scene.id: scene for scene in resume_from.scenes if scene.is_planned}

    def _report(self, scenes: int, phase: str) -> None:
        if self._on_progress is not None:
            self._on_progress(scenes, phase)

    @staticmethod
    def _profiles(library: CharacterLibrary | None) -> dict[str, CharacterProfile]:
        if library is None:
            return {}
        return {profile.id.strip().lower(): profile for profile in library.characters}

    @staticmethod
    def _locations(movie: Movie) -> dict[str, Location]:
        return {location.id.strip().lower(): location for location in movie.locations}
