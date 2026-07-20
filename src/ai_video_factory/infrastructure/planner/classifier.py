"""Decide what each scene is doing (pure, no I/O).

Coverage follows content: a fight is covered differently from a conversation,
and a vista differently from a moment of grief. This reads the scene's own
words — its action, dialogue, emotion, cast and location — and names the kind,
which the framing rules then key off.

Nothing is invented. Every kind is decided from text the story already
contains; when nothing distinguishes a scene it is treated as ``ACTION``, the
kind that keeps the character in a visible world rather than in a portrait.
"""

from __future__ import annotations

from ai_video_factory.domain.value_objects.movie import Scene
from ai_video_factory.domain.value_objects.shot_plan import SceneKind
from ai_video_factory.domain.value_objects.storyboard import StoryboardShot

COMBAT_WORDS: frozenset[str] = frozenset(
    {
        "fight",
        "battle",
        "combat",
        "strike",
        "attack",
        "clash",
        "duel",
        "sword",
        "blade",
        "punch",
        "kick",
        "slash",
        "blast",
        "defend",
        "block",
        "charge at",
        "spell",
        "explode",
        "explosion",
    }
)

ACTION_WORDS: frozenset[str] = frozenset(
    {
        "run",
        "ride",
        "chase",
        "flee",
        "escape",
        "leap",
        "jump",
        "fly",
        "climb",
        "drive",
        "race",
        "walk",
        "steer",
        "dodge",
        "land",
        "rush",
        "sprint",
    }
)

EMOTION_WORDS: frozenset[str] = frozenset(
    {
        "grief",
        "tears",
        "weep",
        "cry",
        "sorrow",
        "shock",
        "shocked",
        "realise",
        "realize",
        "remember",
        "mourn",
        "despair",
        "longing",
        "heartbreak",
        "stare",
        "whisper",
    }
)

LANDSCAPE_WORDS: frozenset[str] = frozenset(
    {
        "vista",
        "horizon",
        "skyline",
        "mountain",
        "valley",
        "sea",
        "ocean",
        "desert",
        "forest",
        "city from above",
        "panorama",
        "sky",
        "cliff",
        "expanse",
    }
)


def _text(scene: Scene, shots: tuple[StoryboardShot, ...]) -> str:
    """Everything the scene says about itself, lowercased."""
    parts = [scene.action, scene.emotion, scene.dialogue, scene.location]
    for shot in shots:
        parts.extend([shot.action, shot.expression, shot.environment])
    return " ".join(part for part in parts if part).lower()


def _hits(text: str, words: frozenset[str]) -> int:
    return sum(1 for word in words if word in text)


def classify_scene(
    scene: Scene,
    shots: tuple[StoryboardShot, ...],
    *,
    is_first_scene: bool = False,
) -> SceneKind:
    """Name what ``scene`` is doing, from its own words.

    The film's first scene is always an opening — it has to place the audience
    somewhere before anything it shows can mean anything.
    """
    if is_first_scene:
        return SceneKind.OPENING

    text = _text(scene, shots)
    combat = _hits(text, COMBAT_WORDS)
    action = _hits(text, ACTION_WORDS)
    emotion = _hits(text, EMOTION_WORDS)
    landscape = _hits(text, LANDSCAPE_WORDS)

    # Combat is a special case of action and outranks it: a fight covered as
    # generic movement loses the geography that makes it readable.
    if combat:
        return SceneKind.COMBAT
    if landscape > max(action, emotion) and landscape >= 2:
        return SceneKind.LANDSCAPE
    if _is_conversation(scene, action):
        return SceneKind.CONVERSATION
    if emotion > action:
        return SceneKind.EMOTION
    if action:
        return SceneKind.ACTION
    if emotion:
        return SceneKind.EMOTION
    return SceneKind.ACTION


def _is_conversation(scene: Scene, action_hits: int) -> bool:
    """Whether the scene is people talking rather than people doing.

    Dialogue alone is not a conversation — a line shouted mid-chase is still a
    chase. It takes speech, more than one person present, and no stronger
    physical action in the scene.
    """
    return bool(scene.dialogue.strip()) and len(scene.characters) > 1 and action_hits == 0


def classify_scenes(
    scenes: tuple[Scene, ...],
    shots_by_scene: dict[int, tuple[StoryboardShot, ...]],
) -> dict[int, SceneKind]:
    """Name every scene, marking the first as the opening."""
    kinds: dict[int, SceneKind] = {}
    for index, scene in enumerate(scenes):
        kinds[scene.id] = classify_scene(
            scene,
            shots_by_scene.get(scene.id, ()),
            is_first_scene=index == 0,
        )
    return kinds
