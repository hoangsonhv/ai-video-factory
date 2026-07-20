"""Build each shot's visual context from its neighbours (pure, no I/O).

A shot rendered from its own description alone has nothing to match: the face,
the coat, the light and the weather are all re-invented. This module gives
every shot an explicit view of the shot before it and the shot after it, plus
the continuity that must survive the cut — so the prompt can say *keep this*
rather than describing the world afresh each time.

Continuity is stated **only where a neighbour exists inside the same scene**.
Across a scene cut the world may legitimately change, and asserting continuity
there would fight the story rather than serve it.
"""

from __future__ import annotations

from collections.abc import Sequence

from ai_video_factory.domain.value_objects.continuity import (
    CharacterBible,
    ShotSummary,
    VisualContext,
    VisualContextDocument,
    WorldBible,
)
from ai_video_factory.domain.value_objects.storyboard import Storyboard, StoryboardShot


def _summary(shot: StoryboardShot | None) -> ShotSummary:
    if shot is None:
        return ShotSummary()
    return ShotSummary(
        shot_id=shot.id,
        scene_id=shot.scene_id,
        camera=shot.camera,
        action=shot.action,
        expression=shot.expression,
        lighting=shot.lighting,
        environment=shot.environment,
    )


def _clean(value: str) -> str:
    return " ".join(value.split()).strip()


def scene_goal(storyboard: Storyboard, scene_id: int) -> str:
    """What the scene is trying to do, read from its own shots.

    Built from the narration spoken across the scene and the actions its shots
    perform — the storyboard's own words, not a fresh interpretation.
    """
    shots = [shot for shot in storyboard.shots if shot.scene_id == scene_id]
    spoken = " ".join(dict.fromkeys(shot.subtitle for shot in shots if shot.subtitle))
    actions = ", ".join(dict.fromkeys(shot.action for shot in shots if shot.action))
    if spoken and actions:
        return _clean(f"{actions} — while the narration says: {spoken}")
    return _clean(spoken or actions)


def character_state(
    shot: StoryboardShot, bible: CharacterBible, previous: StoryboardShot | None
) -> str:
    """Who is on screen and what about them must not change.

    Restates the bible entry for each character present, and — when the shot
    before it in the same scene showed them too — says explicitly that nothing
    about them has changed since.
    """
    names = [part.strip() for part in shot.character.replace(",", " ").split() if part.strip()]
    states: list[str] = []
    for name in dict.fromkeys(names):
        entry = bible.get(name)
        if entry is None:
            continue
        state = f"{entry.name or entry.id}: {entry.identity}" if entry.identity else entry.name
        if (
            previous is not None
            and previous.scene_id == shot.scene_id
            and name in previous.character
        ):
            state += " — unchanged since the previous shot"
        states.append(_clean(state))
    return "; ".join(states)


def _continuity(
    current: str, previous: StoryboardShot | None, attribute: str, scene_id: int, label: str
) -> str:
    """State what carries over from the previous shot of the same scene."""
    if previous is None or previous.scene_id != scene_id:
        return _clean(current)
    carried = _clean(getattr(previous, attribute, ""))
    if not carried:
        return _clean(current)
    if _clean(current) and _clean(current).lower() != carried.lower():
        return f"{_clean(current)} (continuing from {label}: {carried})"
    return f"unchanged from the previous shot: {carried}"


def build_visual_context(
    storyboard: Storyboard, bible: CharacterBible, world: WorldBible
) -> VisualContextDocument:
    """Give every shot an explicit view of its neighbours and what must carry."""
    shots: Sequence[StoryboardShot] = storyboard.shots
    contexts: list[VisualContext] = []

    for index, shot in enumerate(shots):
        previous = shots[index - 1] if index > 0 else None
        following = shots[index + 1] if index + 1 < len(shots) else None
        same_scene_previous = (
            previous if previous is not None and previous.scene_id == shot.scene_id else None
        )
        location = world.location(str(shot.scene_id))

        contexts.append(
            VisualContext(
                shot_id=shot.id,
                scene_id=shot.scene_id,
                previous_shot=_summary(previous),
                current_shot=_summary(shot),
                next_shot=_summary(following),
                scene_goal=scene_goal(storyboard, shot.scene_id),
                character_state=character_state(shot, bible, previous),
                emotion=_clean(shot.expression),
                camera_continuity=_continuity(
                    shot.camera, same_scene_previous, "camera", shot.scene_id, "the previous setup"
                ),
                lighting_continuity=_continuity(
                    shot.lighting, same_scene_previous, "lighting", shot.scene_id, "the same key"
                ),
                color_continuity=_clean(world.palette),
                weather_continuity=_clean((location.weather if location else "") or world.weather),
                prop_continuity=_continuity(
                    "", same_scene_previous, "environment", shot.scene_id, "the same dressing"
                ),
                environment_continuity=_continuity(
                    shot.environment,
                    same_scene_previous,
                    "environment",
                    shot.scene_id,
                    "the same surroundings",
                ),
            )
        )

    return VisualContextDocument(title=storyboard.title, shots=tuple(contexts))
