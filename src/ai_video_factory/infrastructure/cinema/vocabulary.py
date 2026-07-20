"""Cinematic vocabulary and the rules for choosing from it (pure, no I/O).

A director does not reach for the same lens every time. These helpers pick a
size, angle, lens and composition from the shot's role in its scene, then vary
the choice so consecutive shots do not repeat — the difference between coverage
and a slideshow.

Two rules are enforced rather than hoped for:

- **85mm is never a default.** It is reachable only for a close up or an
  extreme close up, and even there it alternates with 135mm, so a film cannot
  end up shot entirely on one portrait lens.
- **A shot is never merely "standing".** Static verbs are replaced with an
  active one drawn from the scene's own words, because a still subject gives an
  image generator nothing to animate and a video model nothing to move.
"""

from __future__ import annotations

from ai_video_factory.domain.value_objects.cinema import (
    CameraAngle,
    Composition,
    Lens,
    LightingSetup,
    ShotType,
)

ACTIVE_VERBS: tuple[str, ...] = (
    "walking",
    "running",
    "jumping",
    "drawing a sword",
    "casting a spell",
    "turning",
    "looking back",
    "opening a door",
    "holding a phone",
    "kneeling",
    "flying",
    "landing",
)
"""The active vocabulary a static description is replaced from."""

STATIC_WORDS: frozenset[str] = frozenset(
    {"standing", "stands", "stand", "posing", "poses", "idle", "still", "sitting still", "waiting"}
)
"""Descriptions that give nothing to animate."""

# Lenses that suit each shot size. 85mm appears only where a portrait lens is
# genuinely right, and never alone, so it can never become the house default.
_LENS_BY_SHOT: dict[ShotType, tuple[Lens, ...]] = {
    ShotType.ESTABLISHING: (Lens.MM24,),
    ShotType.WIDE: (Lens.MM24, Lens.MM35),
    ShotType.FULL_BODY: (Lens.MM35, Lens.MM50),
    ShotType.MEDIUM: (Lens.MM50, Lens.MM35),
    ShotType.CLOSE_UP: (Lens.MM85, Lens.MM135),
    ShotType.EXTREME_CLOSE_UP: (Lens.MM135, Lens.MM85),
}

# The shape of coverage inside a scene: open wide, work in, punctuate.
_SHOT_CYCLE: tuple[ShotType, ...] = (
    ShotType.WIDE,
    ShotType.MEDIUM,
    ShotType.CLOSE_UP,
    ShotType.FULL_BODY,
    ShotType.MEDIUM,
    ShotType.EXTREME_CLOSE_UP,
    ShotType.WIDE,
    ShotType.MEDIUM,
)

_ANGLE_CYCLE: tuple[CameraAngle, ...] = (
    CameraAngle.EYE_LEVEL,
    CameraAngle.LOW_ANGLE,
    CameraAngle.OVER_SHOULDER,
    CameraAngle.HIGH_ANGLE,
    CameraAngle.TRACKING,
    CameraAngle.DUTCH,
    CameraAngle.DRONE,
)

_COMPOSITION_CYCLE: tuple[Composition, ...] = (
    Composition.RULE_OF_THIRDS,
    Composition.LEADING_LINES,
    Composition.FOREGROUND,
    Composition.NEGATIVE_SPACE,
    Composition.BACKGROUND,
)

# Emotional registers that pull the camera off eye level.
_ANGLE_BY_EMOTION: dict[str, CameraAngle] = {
    "power": CameraAngle.LOW_ANGLE,
    "triumph": CameraAngle.LOW_ANGLE,
    "defiant": CameraAngle.LOW_ANGLE,
    "fear": CameraAngle.HIGH_ANGLE,
    "vulnerable": CameraAngle.HIGH_ANGLE,
    "defeat": CameraAngle.HIGH_ANGLE,
    "tense": CameraAngle.DUTCH,
    "chaos": CameraAngle.DUTCH,
    "menacing": CameraAngle.DUTCH,
}

_LIGHT_BY_WORD: tuple[tuple[tuple[str, ...], LightingSetup], ...] = (
    (("sunset", "golden", "dusk", "dawn", "sunrise"), LightingSetup.SUNSET),
    (("night", "dark", "neon", "midnight"), LightingSetup.NIGHT),
    (("fire", "ember", "flame", "burning"), LightingSetup.FIRE),
    (("moon", "moonlit"), LightingSetup.MOONLIGHT),
    (("shaft", "god ray", "volumetric", "fog", "mist"), LightingSetup.VOLUMETRIC),
    (("rim", "backlit", "silhouette"), LightingSetup.BACK),
    (("soft", "diffuse", "overcast"), LightingSetup.FILL),
)


def choose_shot_type(
    order: int, shot_count: int, is_scene_opening: bool, scene_position: int = 0
) -> ShotType:
    """Pick the shot size from where the shot sits in its scene and film.

    A scene opens on something that establishes it. Everything after that walks
    the coverage cycle **offset by the scene's position**, so scene two does not
    repeat scene one shot for shot — without the offset every scene of equal
    length would be filmed identically, which is a template rather than
    direction.
    """
    if is_scene_opening:
        return ShotType.ESTABLISHING if shot_count > 2 else ShotType.WIDE
    return _SHOT_CYCLE[(order - 1 + scene_position) % len(_SHOT_CYCLE)]


def choose_angle(
    order: int, emotion: str, shot_type: ShotType, scene_position: int = 0
) -> CameraAngle:
    """Pick the angle from the emotion, falling back to varied coverage.

    An emotional register that calls for a particular angle wins; otherwise the
    cycle is offset by the scene's position so consecutive scenes are not
    covered from the same three positions.
    """
    lowered = emotion.lower()
    for word, angle in _ANGLE_BY_EMOTION.items():
        if word in lowered:
            return angle
    if shot_type is ShotType.ESTABLISHING:
        return CameraAngle.DRONE
    return _ANGLE_CYCLE[(order - 1 + scene_position) % len(_ANGLE_CYCLE)]


def choose_lens(shot_type: ShotType, index: int) -> Lens:
    """Pick a lens that suits the shot size, alternating within it.

    85mm is only ever reachable for a close up or extreme close up, and
    alternates with 135mm there, so it can never become a default.
    """
    options = _LENS_BY_SHOT[shot_type]
    return options[index % len(options)]


def choose_composition(index: int, shot_type: ShotType) -> Composition:
    """Pick a composition, favouring depth on the widest shots."""
    if shot_type in (ShotType.ESTABLISHING, ShotType.WIDE):
        return Composition.LEADING_LINES if index % 2 else Composition.BACKGROUND
    if shot_type is ShotType.EXTREME_CLOSE_UP:
        return Composition.NEGATIVE_SPACE
    return _COMPOSITION_CYCLE[index % len(_COMPOSITION_CYCLE)]


def choose_lighting(description: str) -> LightingSetup:
    """Read the lighting setup out of the scene's own description."""
    lowered = description.lower()
    for words, setup in _LIGHT_BY_WORD:
        if any(word in lowered for word in words):
            return setup
    return LightingSetup.KEY


def is_static(action: str) -> bool:
    """Whether an action gives nothing to animate."""
    lowered = action.lower().strip()
    return not lowered or any(word in lowered for word in STATIC_WORDS)


def activate(action: str, index: int) -> str:
    """Return an active action, replacing a static one.

    A description that already contains a verb is kept — the director's own
    words beat a generic substitute. Only genuinely static text is replaced.
    """
    if not is_static(action):
        return " ".join(action.split()).strip()
    return ACTIVE_VERBS[index % len(ACTIVE_VERBS)]
