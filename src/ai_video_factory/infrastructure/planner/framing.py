"""The framing vocabulary and the rules for choosing from it (pure, no I/O).

Every table here exists to stop one failure: a film shot entirely in portrait.
The sprint's rules are enforced structurally rather than hoped for —

- a scene is covered as the **kind of scene it is** (an opening establishes, a
  fight is full body, a vista is extreme wide, grief is close);
- a lens is chosen from the **shot size**, and **85mm is never a default** — it
  is reachable only on the two closest sizes, and alternates with 135mm there;
- how much of the body is visible follows the size, so "full body shot" cannot
  quietly render as a headshot.
"""

from __future__ import annotations

from ai_video_factory.domain.value_objects.shot_plan import (
    CameraAngle,
    CameraDistance,
    Composition,
    Lens,
    LightingStyle,
    MovementPriority,
    SceneKind,
    ShotType,
    VisibleBody,
)

# The coverage pattern for each kind of scene. The **first** entry is the size
# the sprint mandates for that kind; the rest are the coverage that surrounds
# it, so a scene reads as its kind without every shot in it being identical.
COVERAGE: dict[SceneKind, tuple[ShotType, ...]] = {
    SceneKind.OPENING: (
        ShotType.ESTABLISHING,
        ShotType.WIDE,
        ShotType.FULL_BODY,
        ShotType.MEDIUM,
    ),
    SceneKind.CONVERSATION: (
        ShotType.MEDIUM,
        ShotType.MEDIUM_CLOSE,
        ShotType.WIDE,
        ShotType.MEDIUM,
    ),
    SceneKind.ACTION: (
        ShotType.WIDE,
        ShotType.FULL_BODY,
        ShotType.MEDIUM,
        ShotType.WIDE,
    ),
    SceneKind.COMBAT: (
        ShotType.FULL_BODY,
        ShotType.WIDE,
        ShotType.MEDIUM,
        ShotType.FULL_BODY,
    ),
    SceneKind.EMOTION: (
        ShotType.CLOSE_UP,
        ShotType.MEDIUM_CLOSE,
        ShotType.MEDIUM,
        ShotType.WIDE,
    ),
    SceneKind.LANDSCAPE: (
        ShotType.EXTREME_WIDE,
        ShotType.WIDE,
        ShotType.ESTABLISHING,
        ShotType.FULL_BODY,
    ),
}

MANDATED: dict[SceneKind, ShotType] = {kind: sizes[0] for kind, sizes in COVERAGE.items()}
"""The size the sprint requires each kind of scene to open on."""

# Lenses that suit each size. 85mm appears only on the two closest sizes and
# never alone, so no film can end up shot on one portrait lens.
LENS_BY_SHOT: dict[ShotType, tuple[Lens, ...]] = {
    ShotType.ESTABLISHING: (Lens.MM18, Lens.MM24),
    ShotType.EXTREME_WIDE: (Lens.MM18, Lens.MM24),
    ShotType.WIDE: (Lens.MM24, Lens.MM35),
    ShotType.FULL_BODY: (Lens.MM35, Lens.MM50),
    ShotType.MEDIUM: (Lens.MM50, Lens.MM35),
    ShotType.MEDIUM_CLOSE: (Lens.MM50, Lens.MM85),
    ShotType.CLOSE_UP: (Lens.MM85, Lens.MM135),
    ShotType.EXTREME_CLOSE: (Lens.MM135, Lens.MM85),
}

DISTANCE_BY_SHOT: dict[ShotType, CameraDistance] = {
    ShotType.ESTABLISHING: CameraDistance.VERY_FAR,
    ShotType.EXTREME_WIDE: CameraDistance.VERY_FAR,
    ShotType.WIDE: CameraDistance.FAR,
    ShotType.FULL_BODY: CameraDistance.FAR,
    ShotType.MEDIUM: CameraDistance.MEDIUM,
    ShotType.MEDIUM_CLOSE: CameraDistance.NEAR,
    ShotType.CLOSE_UP: CameraDistance.NEAR,
    ShotType.EXTREME_CLOSE: CameraDistance.VERY_NEAR,
}

BODY_BY_SHOT: dict[ShotType, VisibleBody] = {
    ShotType.ESTABLISHING: VisibleBody.FULL_BODY,
    ShotType.EXTREME_WIDE: VisibleBody.FULL_BODY,
    ShotType.WIDE: VisibleBody.FULL_BODY,
    ShotType.FULL_BODY: VisibleBody.FULL_BODY,
    ShotType.MEDIUM: VisibleBody.WAIST_UP,
    ShotType.MEDIUM_CLOSE: VisibleBody.CHEST_UP,
    ShotType.CLOSE_UP: VisibleBody.HEAD_AND_SHOULDERS,
    ShotType.EXTREME_CLOSE: VisibleBody.DETAIL,
}

COMPOSITION_BY_SHOT: dict[ShotType, tuple[Composition, ...]] = {
    ShotType.ESTABLISHING: (Composition.DEEP_BACKGROUND, Composition.LEADING_LINES),
    ShotType.EXTREME_WIDE: (Composition.NEGATIVE_SPACE, Composition.SYMMETRY),
    ShotType.WIDE: (Composition.LEADING_LINES, Composition.DEPTH_LAYERS),
    ShotType.FULL_BODY: (Composition.RULE_OF_THIRDS, Composition.FOREGROUND_FRAMING),
    ShotType.MEDIUM: (Composition.RULE_OF_THIRDS, Composition.DEPTH_LAYERS),
    ShotType.MEDIUM_CLOSE: (Composition.RULE_OF_THIRDS, Composition.FOREGROUND_FRAMING),
    ShotType.CLOSE_UP: (Composition.NEGATIVE_SPACE, Composition.RULE_OF_THIRDS),
    ShotType.EXTREME_CLOSE: (Composition.NEGATIVE_SPACE, Composition.SYMMETRY),
}

# Emotional registers that pull the camera off eye level.
ANGLE_BY_EMOTION: tuple[tuple[tuple[str, ...], CameraAngle], ...] = (
    (("power", "triumph", "defiant", "rise", "victorious"), CameraAngle.LOW_ANGLE),
    (("fear", "vulnerable", "defeat", "lost", "small"), CameraAngle.HIGH_ANGLE),
    (("tense", "chaos", "menacing", "unsettl", "wrong"), CameraAngle.DUTCH),
)

ANGLE_CYCLE: tuple[CameraAngle, ...] = (
    CameraAngle.EYE_LEVEL,
    CameraAngle.LOW_ANGLE,
    CameraAngle.OVER_SHOULDER,
    CameraAngle.HIGH_ANGLE,
    CameraAngle.GROUND_LEVEL,
    CameraAngle.DUTCH,
)

LIGHT_BY_WORD: tuple[tuple[tuple[str, ...], LightingStyle], ...] = (
    (("neon", "signage", "magenta"), LightingStyle.NEON),
    # "golden" alone is a colour, not a time of day — matching it turned a
    # midnight cemetery lit by a phone screen into golden hour.
    (("sunset", "golden hour", "dusk", "dawn", "sunrise"), LightingStyle.GOLDEN_HOUR),
    (("moon", "moonlit", "moonlight"), LightingStyle.MOONLIGHT),
    (("fire", "ember", "flame", "burning", "torch"), LightingStyle.FIRELIGHT),
    (("shaft", "god ray", "volumetric", "fog", "mist"), LightingStyle.VOLUMETRIC),
    (("rim", "backlit", "silhouette"), LightingStyle.RIM),
    (("soft", "diffuse", "overcast", "grey", "gray"), LightingStyle.OVERCAST),
    (("night", "dark", "midnight", "shadow"), LightingStyle.NIGHT_AMBIENT),
)

MOTION_BY_SHOT: dict[ShotType, str] = {
    ShotType.ESTABLISHING: "slow aerial drift revealing the space",
    ShotType.EXTREME_WIDE: "very slow push across the vista",
    ShotType.WIDE: "slow push in, holding the geography",
    ShotType.FULL_BODY: "tracking alongside the subject at full height",
    ShotType.MEDIUM: "gentle handheld follow",
    ShotType.MEDIUM_CLOSE: "slow drift in",
    ShotType.CLOSE_UP: "almost still, breathing with the subject",
    ShotType.EXTREME_CLOSE: "micro push in, holding on the detail",
}

# Words in a shot's own action that say what the frame is really moving.
_ENVIRONMENT_MOTION_WORDS: frozenset[str] = frozenset(
    {"fog", "rain", "snow", "wind", "traffic", "crowd", "smoke", "dust", "leaves", "runes"}
)
_CAMERA_MOTION_WORDS: frozenset[str] = frozenset(
    {"pan", "tilt", "dolly", "crane", "orbit", "zoom", "track", "drone", "aerial"}
)
_STATIC_WORDS: frozenset[str] = frozenset(
    {"standing", "stands", "stand", "posing", "idle", "still", "waiting", "watching"}
)


def coverage_for(
    kind: SceneKind, position: int, shot_count: int, is_scene_opening: bool
) -> ShotType:
    """Pick the size for a shot from its scene's kind and its place in it.

    The scene's opening shot always takes the size the sprint mandates for that
    kind; the rest walk that kind's coverage pattern. A two-shot scene keeps the
    mandated size and one contrasting size, so even a short scene is covered.
    """
    pattern = COVERAGE[kind]
    if is_scene_opening:
        return pattern[0]
    step = position % max(1, len(pattern) - 1)
    return pattern[1 + step] if shot_count > 1 else pattern[0]


def lens_for(shot_type: ShotType, used: int) -> Lens:
    """Pick a lens suiting the size, alternating **within** that size.

    Counting per size rather than by position in the film is what keeps the
    long lenses reachable: indexing globally makes every close up land on the
    same parity, and one lens silently becomes the house default.
    """
    options = LENS_BY_SHOT[shot_type]
    return options[used % len(options)]


def distance_for(shot_type: ShotType) -> CameraDistance:
    """How far the camera stands for this size."""
    return DISTANCE_BY_SHOT[shot_type]


def body_for(shot_type: ShotType) -> VisibleBody:
    """How much of the character this size shows."""
    return BODY_BY_SHOT[shot_type]


def composition_for(shot_type: ShotType, index: int) -> Composition:
    """Pick a composition that suits the size."""
    options = COMPOSITION_BY_SHOT[shot_type]
    return options[index % len(options)]


def angle_for(emotion: str, shot_type: ShotType, index: int) -> CameraAngle:
    """Pick the angle from the emotion, falling back to varied coverage."""
    lowered = emotion.lower()
    for words, angle in ANGLE_BY_EMOTION:
        if any(word in lowered for word in words):
            return angle
    if shot_type is ShotType.ESTABLISHING:
        return CameraAngle.AERIAL
    if shot_type is ShotType.EXTREME_WIDE:
        return CameraAngle.EYE_LEVEL
    return ANGLE_CYCLE[index % len(ANGLE_CYCLE)]


def lighting_for(description: str) -> LightingStyle:
    """Read the lighting style out of the scene's own description.

    Pass the lighting *and* the environment: a shot lit by "a golden glow from
    a phone screen" names no style on its own, while the fog it stands in does.
    """
    lowered = description.lower()
    for words, style in LIGHT_BY_WORD:
        if any(word in lowered for word in words):
            return style
    return LightingStyle.KEY


def motion_for(shot_type: ShotType, camera_motion: str) -> str:
    """The camera move: the storyboard's own, else the one the size implies."""
    stated = " ".join(camera_motion.split()).strip()
    if stated and stated.lower() not in {"static", "none", "fixed"}:
        return stated
    return MOTION_BY_SHOT[shot_type]


def priority_for(action: str, camera_motion: str, environment: str) -> MovementPriority:
    """What the frame is primarily moving, so a video model knows what to animate."""
    lowered = f"{action} {environment}".lower()
    motion = camera_motion.lower()
    if any(word in motion for word in _CAMERA_MOTION_WORDS):
        return MovementPriority.CAMERA
    if any(word in lowered for word in _STATIC_WORDS):
        # Nothing in the subject moves, so the world has to carry the frame.
        if any(word in lowered for word in _ENVIRONMENT_MOTION_WORDS):
            return MovementPriority.ENVIRONMENT
        return MovementPriority.STILLNESS
    if any(word in lowered for word in _ENVIRONMENT_MOTION_WORDS):
        return MovementPriority.ENVIRONMENT
    return MovementPriority.SUBJECT
