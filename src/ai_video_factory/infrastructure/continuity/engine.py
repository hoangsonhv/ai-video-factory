"""The Visual Continuity Engine (infrastructure service).

Turns a storyboard plus the two bibles into three artifacts:

- ``visual_context.json`` — what each shot must match, forwards and backwards;
- ``shot_image_prompts.json`` — one prompt per shot, built from every source;
- ``prompt_scores.json`` — how well each prompt carries continuity.

Deterministic and offline: no provider is contacted, so the same inputs always
give the same prompts. Each prompt is written once by the shared prompt builder
and then scored; a shortfall is **reported rather than looped over**, because
its cause is missing source data that no rephrasing can supply.
"""

from __future__ import annotations

import logging

from ai_video_factory.domain.value_objects.character_library import CharacterLibrary
from ai_video_factory.domain.value_objects.continuity import (
    CharacterBible,
    PromptScore,
    PromptScoreDocument,
    VisualContext,
    VisualContextDocument,
    WorldBible,
)
from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.domain.value_objects.movie import Movie
from ai_video_factory.domain.value_objects.storyboard import Storyboard
from ai_video_factory.infrastructure.continuity.bibles import (
    build_character_bible,
    build_world_bible,
)
from ai_video_factory.infrastructure.continuity.context import build_visual_context
from ai_video_factory.infrastructure.continuity.errors import ContinuityError
from ai_video_factory.infrastructure.continuity.prompt_composer import (
    PromptSource,
    build_prompt,
)
from ai_video_factory.infrastructure.continuity.scorer import PASS_THRESHOLD, score_prompt

_logger = logging.getLogger(__name__)


class ContinuityResult:
    """Everything one run produced."""

    def __init__(
        self,
        character_bible: CharacterBible,
        world_bible: WorldBible,
        context: VisualContextDocument,
        prompts: tuple[ImagePrompt, ...],
        scores: PromptScoreDocument,
    ) -> None:
        self.character_bible = character_bible
        self.world_bible = world_bible
        self.context = context
        self.prompts = prompts
        self.scores = scores


class VisualContinuityEngine:
    """Builds continuity-aware image prompts and scores them."""

    def __init__(self, *, threshold: int = PASS_THRESHOLD) -> None:
        self._threshold = threshold

    def derive_bibles(
        self, library: CharacterLibrary, movie: Movie
    ) -> tuple[CharacterBible, WorldBible]:
        """Build both bibles from the artifacts already on disk."""
        return build_character_bible(library, movie), build_world_bible(movie)

    def run(
        self,
        storyboard: Storyboard,
        character_bible: CharacterBible,
        world_bible: WorldBible,
    ) -> ContinuityResult:
        """Build the contexts, compose every prompt, and score them.

        Raises:
            ContinuityError: If the storyboard carries no shots.
        """
        if not storyboard.shots:
            raise ContinuityError(
                "storyboard carries no shots; run `storyboard` before the continuity engine"
            )

        context = build_visual_context(storyboard, character_bible, world_bible)
        prompts: list[ImagePrompt] = []
        scores: list[PromptScore] = []

        for shot_context in context.shots:
            prompt = build_prompt(self._source(shot_context), character_bible, world_bible)
            score = score_prompt(prompt, shot_context, character_bible, world_bible, attempts=1)
            prompts.append(
                ImagePrompt(
                    scene_number=shot_context.shot_id,
                    prompt=prompt,
                    negative_prompt=world_bible.negative_prompt,
                    aspect_ratio="9:16",
                    style=world_bible.style,
                    camera=shot_context.current_shot.camera,
                    lighting=shot_context.lighting_continuity,
                    character_reference=shot_context.character_state,
                    environment=shot_context.environment_continuity,
                )
            )
            scores.append(score)

        return ContinuityResult(
            character_bible=character_bible,
            world_bible=world_bible,
            context=context,
            prompts=tuple(prompts),
            scores=PromptScoreDocument(threshold=self._threshold, scores=tuple(scores)),
        )

    @staticmethod
    def _source(shot_context: VisualContext) -> PromptSource:
        """Adapt a visual context into what the prompt builder asks for."""
        current = shot_context.current_shot
        return PromptSource(
            character_id=shot_context.character_state,
            action=current.action,
            environment=shot_context.environment_continuity or current.environment,
            camera=current.camera,
            lighting=shot_context.lighting_continuity or current.lighting,
            composition="",
            allows_close_framing="close" in current.camera.lower(),
        )
