"""The Character Memory Engine (infrastructure service).

Freezes each character's canonical look, adopts the first generated image of
them as the reference, and rewrites every prompt to restate that identity.
A prompt that scores below the threshold is rebuilt with the appearance stated
more insistently — the same escalation the continuity engine uses, so a retry
genuinely changes the text.

Deterministic and offline: no provider is contacted, no image is generated, no
video or compose stage is touched.
"""

from __future__ import annotations

import logging

from ai_video_factory.domain.value_objects.character_memory import (
    AppearanceScore,
    AppearanceScoreDocument,
    CharacterMemory,
    CharacterMemoryDocument,
)
from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.domain.value_objects.storyboard import Storyboard
from ai_video_factory.infrastructure.memory.enricher import MAX_LEVEL, enrich_prompt
from ai_video_factory.infrastructure.memory.errors import CharacterMemoryError
from ai_video_factory.infrastructure.memory.validator import PASS_THRESHOLD, AppearanceValidator

_logger = logging.getLogger(__name__)


class MemoryResult:
    """Everything one run produced."""

    def __init__(
        self,
        memory: CharacterMemoryDocument,
        prompts: tuple[ImagePrompt, ...],
        scores: AppearanceScoreDocument,
    ) -> None:
        self.memory = memory
        self.prompts = prompts
        self.scores = scores


class CharacterMemoryEngine:
    """Rewrites prompts so every image of a character matches the first."""

    def __init__(
        self,
        *,
        threshold: int = PASS_THRESHOLD,
        max_level: int = MAX_LEVEL,
        provider: str = "",
    ) -> None:
        self._validator = AppearanceValidator(threshold=threshold)
        self._threshold = threshold
        self._max_level = max_level
        self._provider = provider

    def run(
        self,
        storyboard: Storyboard,
        prompts: tuple[ImagePrompt, ...],
        memory: CharacterMemoryDocument,
    ) -> MemoryResult:
        """Enrich every prompt with remembered identity and score the result.

        Raises:
            CharacterMemoryError: If there are no prompts to enrich.
        """
        if not prompts:
            raise CharacterMemoryError(
                "no prompts to enrich; run `continuity` before the memory engine"
            )

        by_shot = {shot.id: shot for shot in storyboard.shots}
        enriched: list[ImagePrompt] = []
        scores: list[AppearanceScore] = []
        # What the last prompt said about each character, fed forward so a
        # shot can be told what its predecessor established.
        previous_appearance: dict[str, str] = {}

        for prompt in prompts:
            shot = by_shot.get(prompt.scene_number)
            character = self._character_for(shot.character if shot else "", memory)
            if character is None:
                enriched.append(prompt)
                continue

            text, score = self._enrich_until_scored(
                prompt.prompt,
                character,
                previous_appearance.get(character.character_id, ""),
                shot_id=prompt.scene_number,
                scene_id=shot.scene_id if shot else 0,
            )
            enriched.append(prompt.model_copy(update={"prompt": text}))
            scores.append(score)
            previous_appearance[character.character_id] = character.summary

        return MemoryResult(
            memory=memory,
            prompts=tuple(enriched),
            scores=AppearanceScoreDocument(threshold=self._threshold, scores=tuple(scores)),
        )

    @staticmethod
    def _character_for(names: str, memory: CharacterMemoryDocument) -> CharacterMemory | None:
        """The first remembered character named in a shot."""
        for part in names.replace(",", " ").split():
            found = memory.get(part.strip())
            if found is not None:
                return found
        return None

    def _enrich_until_scored(
        self,
        prompt: str,
        character: CharacterMemory,
        previous: str,
        *,
        shot_id: int,
        scene_id: int,
    ) -> tuple[str, AppearanceScore]:
        """Enrich, validate, and escalate until the appearance is pinned."""
        text = enrich_prompt(
            prompt,
            character,
            provider=self._provider,
            previous_appearance=previous,
            level=0,
        )
        best_text = text
        best = self._validator.validate(
            text,
            character,
            shot_id=shot_id,
            scene_id=scene_id,
            attempts=1,
        )
        if best.passed(self._threshold):
            return best_text, best

        for level in range(1, self._max_level + 1):
            text = enrich_prompt(
                prompt,
                character,
                provider=self._provider,
                previous_appearance=previous,
                level=level,
            )
            score = self._validator.validate(
                text,
                character,
                shot_id=shot_id,
                scene_id=scene_id,
                attempts=level + 1,
            )
            if score.total > best.total:
                best_text, best = text, score
            if score.passed(self._threshold):
                return text, score
            _logger.info(
                "shot %d appearance scored %d (<%d) at level %d; rebuilding",
                shot_id,
                score.total,
                self._threshold,
                level,
            )

        # ``attempts`` records how many rebuilds happened, not which one won.
        return best_text, best.model_copy(update={"attempts": self._max_level + 1})
