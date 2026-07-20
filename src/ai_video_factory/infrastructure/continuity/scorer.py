"""Score a composed prompt for continuity (pure, no I/O).

Five dimensions, each scored as the fraction of the elements that dimension
*needs* which the prompt actually supplies. An element counts as supplied when
the prompt states its specific value **or** carries an explicit continuity
directive covering it — so escalating the composer's explicitness genuinely
raises the score rather than rewording the same content.

Crucially, an element the source data never provided still counts against the
score. A storyboard that records no weather really does produce images whose
weather drifts; excluding it from the denominator would hide exactly the
problem this stage exists to surface. A low score therefore points at missing
upstream data, and :attr:`PromptScore.issues` names which.
"""

from __future__ import annotations

from collections.abc import Sequence

from ai_video_factory.domain.value_objects.continuity import (
    CharacterBible,
    PromptScore,
    VisualContext,
    WorldBible,
)

PASS_THRESHOLD = 90
"""Below this the prompt is recomposed at a higher level of explicitness."""

_MATCH_CHARS = 40
"""How much of a value must appear for it to count as stated."""


def _present(prompt: str, value: str) -> bool:
    cleaned = " ".join(value.split()).strip().lower()
    return bool(cleaned) and cleaned[:_MATCH_CHARS] in prompt.lower()


def _score(prompt: str, required: Sequence[tuple[str, str, str]]) -> tuple[int, list[str]]:
    """Score one dimension.

    ``required`` is ``(label, specific value, directive)``. An element is
    satisfied by either its value or the directive that covers it; anything
    neither supplies is missing and named.
    """
    if not required:
        return 100, []
    missing = [
        label
        for label, value, directive in required
        if not _present(prompt, value) and not (directive and directive.lower() in prompt.lower())
    ]
    score = round((len(required) - len(missing)) / len(required) * 100)
    return score, missing


def score_prompt(
    prompt: str,
    context: VisualContext,
    bible: CharacterBible,
    world: WorldBible,
    *,
    attempts: int = 1,
) -> PromptScore:
    """Score ``prompt`` across the five continuity dimensions."""
    identity_directive = "same face, same hair, same wardrobe"
    cast = [
        entry for entry in bible.characters if entry.id.lower() in context.character_state.lower()
    ]
    character, character_missing = _score(
        prompt,
        [
            ("character_state", context.character_state, ""),
            *[(f"wardrobe:{e.id}", e.wardrobe, identity_directive) for e in cast],
            *[(f"appearance:{e.id}", e.appearance, identity_directive) for e in cast],
        ],
    )

    continuity_directive = "same location, same time of day, same weather"
    environment, environment_missing = _score(
        prompt,
        [
            ("environment", context.environment_continuity, continuity_directive),
            ("weather", context.weather_continuity, continuity_directive),
            ("lighting", context.lighting_continuity, continuity_directive),
            ("props", context.prop_continuity, continuity_directive),
        ],
    )

    style_directive = "identical colour grade"
    style, style_missing = _score(
        prompt,
        [
            ("palette", world.palette, style_directive),
            ("art_direction", world.art_direction, style_directive),
            ("cinematic_style", world.cinematic_style, style_directive),
            ("colour_continuity", context.color_continuity, style_directive),
        ],
    )

    story_directive = "follows directly from the previous shot"
    story, story_missing = _score(
        prompt,
        [
            ("scene_goal", context.scene_goal, ""),
            ("previous_shot", context.previous_shot.action, story_directive),
            ("current_shot", context.current_shot.action, ""),
            ("next_shot", context.next_shot.action, story_directive),
            ("emotion", context.emotion, ""),
        ],
    )

    camera_directive = "consistent eyeline and screen direction"
    camera, camera_missing = _score(
        prompt,
        [
            ("camera", context.camera_continuity or context.current_shot.camera, ""),
            ("lens", "lens", ""),
            ("previous_camera", context.previous_shot.camera, camera_directive),
        ],
    )

    return PromptScore(
        shot_id=context.shot_id,
        character_consistency=character,
        environment_consistency=environment,
        style_consistency=style,
        story_continuity=story,
        camera_continuity=camera,
        attempts=attempts,
        issues=tuple(
            character_missing + environment_missing + style_missing + story_missing + camera_missing
        ),
    )
