"""Shot plan value objects (domain layer).

A shot plan is the decision, for every shot in the film, of **how much world
the frame holds** — the size, distance, lens, composition, what of the body is
visible, and what of the environment must read in the foreground, midground and
background.

It exists because a prompt that says only "a character, cinematic" produces a
portrait every time. The plan is what makes a frame a *movie frame*: the camera
is placed for the scene's content, and the whole film's coverage is validated
as a distribution rather than shot by shot.

Pure and immutable (docs/ai-tool.md §2.1) — no I/O, no vendor SDKs. This is the
schema of ``output/shot_plan.json`` and ``output/shot_statistics.json``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SceneKind(StrEnum):
    """What a scene is doing, which decides how it is covered."""

    OPENING = "opening"
    CONVERSATION = "conversation"
    ACTION = "action"
    COMBAT = "combat"
    EMOTION = "emotion"
    LANDSCAPE = "landscape"


class ShotType(StrEnum):
    """How much of the world the frame holds."""

    ESTABLISHING = "establishing"
    EXTREME_WIDE = "extreme_wide"
    WIDE = "wide"
    MEDIUM = "medium"
    MEDIUM_CLOSE = "medium_close"
    CLOSE_UP = "close_up"
    EXTREME_CLOSE = "extreme_close"
    FULL_BODY = "full_body"


CLOSE_SHOTS: frozenset[ShotType] = frozenset({ShotType.CLOSE_UP, ShotType.EXTREME_CLOSE})
"""The sizes that genuinely produce a portrait."""

MEDIUM_SHOTS: frozenset[ShotType] = frozenset({ShotType.MEDIUM, ShotType.MEDIUM_CLOSE})

WIDE_SHOTS: frozenset[ShotType] = frozenset(
    {ShotType.WIDE, ShotType.EXTREME_WIDE, ShotType.FULL_BODY}
)
"""The sizes that put the character in a world rather than in a frame alone."""

SHOT_TYPE_TEXT: dict[ShotType, str] = {
    ShotType.ESTABLISHING: "establishing shot",
    ShotType.EXTREME_WIDE: "extreme wide shot",
    ShotType.WIDE: "wide shot",
    ShotType.MEDIUM: "medium shot",
    ShotType.MEDIUM_CLOSE: "medium close shot",
    ShotType.CLOSE_UP: "close up shot",
    ShotType.EXTREME_CLOSE: "extreme close up shot",
    ShotType.FULL_BODY: "full body shot",
}
"""How each size is written into a prompt.

Deliberately separate from the enum value: the enum is the machine-readable
key (``close_up``), this is the English an image model understands ("close up
shot"). Keeping them apart is also what lets the portrait guard scan for the
English phrasing without tripping over the plan's own vocabulary.
"""


class Lens(StrEnum):
    """The focal length, which decides how the space reads."""

    MM18 = "18mm"
    MM24 = "24mm"
    MM35 = "35mm"
    MM50 = "50mm"
    MM85 = "85mm"
    MM135 = "135mm"


class CameraDistance(StrEnum):
    """How far the camera physically stands from the subject."""

    VERY_FAR = "very far"
    FAR = "far"
    MEDIUM = "medium"
    NEAR = "near"
    VERY_NEAR = "very near"


class CameraAngle(StrEnum):
    """Where the camera stands relative to the subject."""

    EYE_LEVEL = "eye level"
    LOW_ANGLE = "low angle"
    HIGH_ANGLE = "high angle"
    DUTCH = "dutch angle"
    OVER_SHOULDER = "over the shoulder"
    AERIAL = "aerial"
    GROUND_LEVEL = "ground level"


class Composition(StrEnum):
    """How the frame is arranged."""

    RULE_OF_THIRDS = "rule of thirds"
    LEADING_LINES = "leading lines"
    FOREGROUND_FRAMING = "foreground framing"
    DEEP_BACKGROUND = "deep background"
    NEGATIVE_SPACE = "negative space"
    SYMMETRY = "symmetry"
    DEPTH_LAYERS = "layered depth"


class VisibleBody(StrEnum):
    """How much of the character the frame actually shows."""

    FULL_BODY = "full body visible"
    THREE_QUARTER = "three quarter body visible"
    WAIST_UP = "waist up visible"
    CHEST_UP = "chest up visible"
    HEAD_AND_SHOULDERS = "head and shoulders visible"
    DETAIL = "single detail visible"


class LightingStyle(StrEnum):
    """The light that shapes the shot."""

    KEY = "hard key light"
    SOFT_FILL = "soft fill light"
    RIM = "rim back light"
    VOLUMETRIC = "volumetric light shafts"
    GOLDEN_HOUR = "golden hour"
    NIGHT_AMBIENT = "night ambient"
    FIRELIGHT = "firelight"
    MOONLIGHT = "moonlight"
    NEON = "neon practical light"
    OVERCAST = "overcast diffuse light"


class MovementPriority(StrEnum):
    """What the frame is primarily moving, so a video model knows what to animate."""

    SUBJECT = "subject motion"
    CAMERA = "camera motion"
    ENVIRONMENT = "environment motion"
    STILLNESS = "held stillness"


class EnvironmentVisibility(BaseModel):
    """What must be visible at each depth of the frame.

    A frame with nothing at any depth is not a movie frame — it is a portrait
    on a backdrop. That is why an entirely empty visibility rejects its shot.
    """

    model_config = ConfigDict(frozen=True)

    foreground: str = ""
    midground: str = ""
    background: str = ""

    @property
    def is_empty(self) -> bool:
        """Whether no depth of the frame states anything at all."""
        return not any(part.strip() for part in (self.foreground, self.midground, self.background))

    @property
    def summary(self) -> str:
        """The three depths as one line, naming each."""
        parts = (
            ("foreground", self.foreground),
            ("midground", self.midground),
            ("background", self.background),
        )
        return "; ".join(f"{label}: {value}" for label, value in parts if value.strip())


class PlannedShot(BaseModel):
    """Every framing decision for one shot, and why it was made."""

    model_config = ConfigDict(frozen=True)

    shot_id: int = Field(ge=1)
    scene_id: int = Field(ge=1)
    purpose: str = ""
    shot_type: ShotType = ShotType.MEDIUM
    camera_distance: CameraDistance = CameraDistance.MEDIUM
    camera_angle: CameraAngle = CameraAngle.EYE_LEVEL
    lens: Lens = Lens.MM50
    composition: Composition = Composition.RULE_OF_THIRDS
    visible_body: VisibleBody = VisibleBody.WAIST_UP
    camera_motion: str = ""
    focus_subject: str = ""
    environment_visibility: EnvironmentVisibility = Field(default_factory=EnvironmentVisibility)
    lighting_style: LightingStyle = LightingStyle.KEY
    emotion: str = ""
    movement_priority: MovementPriority = MovementPriority.SUBJECT
    reason: str = ""

    @property
    def is_close(self) -> bool:
        """Whether this shot is a genuine close size."""
        return self.shot_type in CLOSE_SHOTS

    @property
    def camera(self) -> str:
        """Size, distance, angle and lens as one camera instruction."""
        return (
            f"{SHOT_TYPE_TEXT[self.shot_type]}, {self.camera_distance.value}, "
            f"{self.camera_angle.value}, {self.lens.value}"
        )


class DistributionReport(BaseModel):
    """Whether the film's coverage is balanced, measured across every shot."""

    model_config = ConfigDict(frozen=True)

    total: int = Field(default=0, ge=0)
    close_pct: float = Field(default=0.0, ge=0.0)
    medium_pct: float = Field(default=0.0, ge=0.0)
    wide_pct: float = Field(default=0.0, ge=0.0)
    establishing_pct: float = Field(default=0.0, ge=0.0)
    issues: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        """Whether every distribution rule holds."""
        return not self.issues


class ShotPlan(BaseModel):
    """The framing decisions for a whole film, and how they were reached."""

    model_config = ConfigDict(frozen=True)

    title: str = ""
    shots: tuple[PlannedShot, ...] = ()
    scene_kinds: dict[int, SceneKind] = Field(default_factory=dict)
    replans: int = Field(default=0, ge=0)
    distribution: DistributionReport = Field(default_factory=DistributionReport)
    notes: tuple[str, ...] = ()

    def shot(self, shot_id: int) -> PlannedShot | None:
        """The plan for ``shot_id``, if there is one."""
        return next((shot for shot in self.shots if shot.shot_id == shot_id), None)

    def scene_shots(self, scene_id: int) -> tuple[PlannedShot, ...]:
        """Every planned shot belonging to ``scene_id``, in order."""
        return tuple(shot for shot in self.shots if shot.scene_id == scene_id)


class ShotStatistics(BaseModel):
    """How the finished plan is distributed, per axis."""

    model_config = ConfigDict(frozen=True)

    total: int = Field(default=0, ge=0)
    shot_types: dict[str, int] = Field(default_factory=dict)
    lenses: dict[str, int] = Field(default_factory=dict)
    cameras: dict[str, int] = Field(default_factory=dict)
    body_visibility: dict[str, int] = Field(default_factory=dict)
    distribution: DistributionReport = Field(default_factory=DistributionReport)
