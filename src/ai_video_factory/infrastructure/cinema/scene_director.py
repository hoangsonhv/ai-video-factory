"""Decide what each scene is *for* (pure, no I/O).

Before any camera is placed, a director asks why the scene exists: what it is
meant to do to the audience, what it is fighting about, and where it falls in
the telling. Those answers are read out of the storyboard's own words and the
scene's position in the film — not invented, so a thin storyboard yields a thin
purpose rather than a confident fiction.
"""

from __future__ import annotations

from collections import Counter

from ai_video_factory.domain.value_objects.cinema import SceneDirection, StoryBeat
from ai_video_factory.domain.value_objects.storyboard import Storyboard, StoryboardShot

# Where a scene falls, as a fraction through the film, and the beat it plays.
_BEATS: tuple[tuple[float, StoryBeat], ...] = (
    (0.10, StoryBeat.SETUP),
    (0.25, StoryBeat.INCITING),
    (0.45, StoryBeat.RISING),
    (0.55, StoryBeat.MIDPOINT),
    (0.80, StoryBeat.ESCALATION),
    (0.95, StoryBeat.CLIMAX),
    (1.01, StoryBeat.RESOLUTION),
)

# What a beat is trying to achieve, stated so a prompt can serve it.
_PURPOSE_BY_BEAT: dict[StoryBeat, str] = {
    StoryBeat.SETUP: "establish the world and who we are following",
    StoryBeat.INCITING: "break the ordinary and set the story moving",
    StoryBeat.RISING: "raise the stakes and commit the character further",
    StoryBeat.MIDPOINT: "turn the story and change what the character wants",
    StoryBeat.ESCALATION: "close off the exits and press the character hardest",
    StoryBeat.CLIMAX: "pay off the conflict at its highest pitch",
    StoryBeat.RESOLUTION: "settle the new world the story leaves behind",
}

# The pressure a scene is under, inferred from its emotional register.
_CONFLICT_BY_EMOTION: tuple[tuple[tuple[str, ...], str], ...] = (
    (("fear", "terror", "panic", "dread"), "survival against a threat"),
    (("anger", "rage", "fury"), "open confrontation"),
    (("resolve", "determined", "defiant"), "the character against their own limits"),
    (("grief", "sorrow", "loss"), "the character against what they cannot undo"),
    (("awe", "wonder", "transcendent"), "the character against something far larger"),
    (("menacing", "cruel", "sinister"), "an antagonist pressing an advantage"),
    (("hope", "triumph", "joy"), "the character claiming what they fought for"),
    (("exhausted", "weary", "fatigued"), "endurance against attrition"),
)


def _dominant(values: list[str]) -> str:
    """The most common non-empty value, ties broken by first appearance."""
    counts = Counter(value for value in values if value.strip())
    return counts.most_common(1)[0][0] if counts else ""


def story_beat(position: int, total: int) -> StoryBeat:
    """The beat a scene plays, from its position in the film."""
    if total <= 0:
        return StoryBeat.RISING
    fraction = position / total
    return next(beat for threshold, beat in _BEATS if fraction <= threshold)


def infer_conflict(emotion: str, actions: list[str]) -> str:
    """Name the pressure the scene is under.

    Read from the emotional register first; failing that, from what the
    characters physically do. When neither says anything the conflict is left
    empty rather than guessed at.
    """
    lowered = emotion.lower()
    for words, conflict in _CONFLICT_BY_EMOTION:
        if any(word in lowered for word in words):
            return conflict
    verbs = " ".join(actions).lower()
    if any(word in verbs for word in ("fight", "strike", "attack", "sword", "battle")):
        return "open confrontation"
    if any(word in verbs for word in ("run", "flee", "escape", "chase")):
        return "pursuit"
    return ""


class SceneDirector:
    """Decides the purpose, emotion, conflict and beat of every scene."""

    def direct(self, storyboard: Storyboard) -> tuple[SceneDirection, ...]:
        """Read each scene's intent out of the storyboard."""
        scene_ids: list[int] = []
        for shot in storyboard.shots:
            if shot.scene_id not in scene_ids:
                scene_ids.append(shot.scene_id)

        directions: list[SceneDirection] = []
        for position, scene_id in enumerate(scene_ids, start=1):
            shots = [shot for shot in storyboard.shots if shot.scene_id == scene_id]
            beat = story_beat(position, len(scene_ids))
            emotion = _dominant([shot.expression for shot in shots])
            directions.append(
                SceneDirection(
                    scene_id=scene_id,
                    purpose=self._purpose(beat, shots),
                    emotion=emotion,
                    conflict=infer_conflict(emotion, [shot.action for shot in shots]),
                    story_beat=beat,
                )
            )
        return tuple(directions)

    @staticmethod
    def _purpose(beat: StoryBeat, shots: list[StoryboardShot]) -> str:
        """What this scene is for, grounded in what it actually shows."""
        intent = _PURPOSE_BY_BEAT[beat]
        subject = _dominant([shot.action for shot in shots])
        return f"{intent} — {subject}" if subject else intent
