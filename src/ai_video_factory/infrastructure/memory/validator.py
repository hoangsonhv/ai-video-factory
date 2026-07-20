"""Validate that a prompt restates a character's remembered appearance.

Eight attributes are compared against the memory: hair, face, clothes, weapon,
colours, gender, age and style. Each scores 100 when the prompt states the
remembered value and 0 when it does not.

An attribute the memory never captured scores **0**, not "not applicable". A
character with no recorded hair really will grow different hair from image to
image, and excusing the gap would report a perfect score for a prompt that
pins nothing. :attr:`AppearanceScore.issues` names each gap so the cause is
visible.
"""

from __future__ import annotations

from collections.abc import Sequence

from ai_video_factory.domain.value_objects.character_memory import (
    AppearanceScore,
    CharacterMemory,
)

PASS_THRESHOLD = 90
"""Below this the prompt is rebuilt with the appearance stated more insistently."""

_MATCH_CHARS = 30
"""How much of a remembered value must appear for it to count as stated."""


def _states(prompt: str, value: str) -> bool:
    cleaned = " ".join(value.split()).strip().lower()
    return bool(cleaned) and cleaned[:_MATCH_CHARS] in prompt.lower()


class AppearanceValidator:
    """Scores how faithfully a prompt restates a remembered appearance."""

    def __init__(self, *, threshold: int = PASS_THRESHOLD) -> None:
        self._threshold = threshold

    @property
    def threshold(self) -> int:
        """The score a prompt must reach."""
        return self._threshold

    def validate(
        self,
        prompt: str,
        memory: CharacterMemory,
        *,
        shot_id: int,
        scene_id: int = 0,
        attempts: int = 1,
    ) -> AppearanceScore:
        """Score ``prompt`` against ``memory`` across the eight attributes."""
        attributes: Sequence[tuple[str, str]] = (
            ("hair", memory.canonical_hair),
            ("face", memory.canonical_face),
            ("clothes", memory.canonical_clothes),
            ("weapon", memory.canonical_weapon),
            ("colors", memory.canonical_color_palette),
            ("gender", memory.gender),
            ("age", memory.age),
            ("style", memory.style),
        )

        results: dict[str, int] = {}
        issues: list[str] = []
        for name, value in attributes:
            stated = _states(prompt, value)
            results[name] = 100 if stated else 0
            if not stated:
                issues.append(name if value.strip() else f"{name} (not remembered)")

        return AppearanceScore(
            shot_id=shot_id,
            scene_id=scene_id,
            character_id=memory.character_id,
            attempts=attempts,
            issues=tuple(issues),
            **results,
        )
