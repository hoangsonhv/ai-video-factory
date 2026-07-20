"""Cinematic direction value objects (domain layer).

What a director decides before a camera is set up: why a scene exists, what it
is fighting about, and — for each shot — the size, angle, lens, composition,
blocking, light and action that serve it.

Pure and immutable (docs/ai-tool.md §2.1) — no I/O, no vendor SDKs. This is the
schema of ``output/cinematic_direction.json``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StoryBeat(StrEnum):
    """Where a scene sits in the telling."""

    SETUP = "setup"
    INCITING = "inciting incident"
    RISING = "rising action"
    MIDPOINT = "midpoint"
    ESCALATION = "escalation"
    CLIMAX = "climax"
    RESOLUTION = "resolution"


class ShotType(StrEnum):
    """How much of the world the frame holds."""

    ESTABLISHING = "establishing shot"
    WIDE = "wide shot"
    MEDIUM = "medium shot"
    FULL_BODY = "full body shot"
    CLOSE_UP = "close up"
    EXTREME_CLOSE_UP = "extreme close up"


class CameraAngle(StrEnum):
    """Where the camera stands relative to the subject."""

    EYE_LEVEL = "eye level"
    LOW_ANGLE = "low angle"
    HIGH_ANGLE = "high angle"
    DUTCH = "dutch angle"
    OVER_SHOULDER = "over the shoulder"
    TRACKING = "tracking"
    DRONE = "drone"


class Lens(StrEnum):
    """The focal length, which decides how the space reads."""

    MM24 = "24mm"
    MM35 = "35mm"
    MM50 = "50mm"
    MM85 = "85mm"
    MM135 = "135mm"


class Composition(StrEnum):
    """How the frame is arranged."""

    RULE_OF_THIRDS = "rule of thirds"
    LEADING_LINES = "leading lines"
    FOREGROUND = "foreground framing"
    BACKGROUND = "deep background"
    NEGATIVE_SPACE = "negative space"


class LightingSetup(StrEnum):
    """The light that shapes the shot."""

    KEY = "hard key light"
    FILL = "soft fill light"
    BACK = "back light rim"
    VOLUMETRIC = "volumetric light shafts"
    SUNSET = "sunset golden hour"
    NIGHT = "night ambient"
    FIRE = "firelight"
    MOONLIGHT = "moonlight"


class Blocking(BaseModel):
    """Where everything sits and how it moves through the frame."""

    model_config = ConfigDict(frozen=True)

    character_position: str = ""
    object_position: str = ""
    movement_path: str = ""

    @property
    def summary(self) -> str:
        """The blocking as one line."""
        parts = (self.character_position, self.object_position, self.movement_path)
        return "; ".join(part for part in parts if part)


class SceneDirection(BaseModel):
    """Why a scene exists and what it is doing to the audience."""

    model_config = ConfigDict(frozen=True)

    scene_id: int = Field(ge=1)
    purpose: str = ""
    emotion: str = ""
    conflict: str = ""
    story_beat: StoryBeat = StoryBeat.RISING


class ShotDirection(BaseModel):
    """Every decision a director makes about one shot.

    The six the sprint requires — purpose, camera, composition, action,
    lighting, emotion — are all present; ``camera`` is the shot type, angle
    and lens taken together.
    """

    model_config = ConfigDict(frozen=True)

    shot_id: int = Field(ge=1)
    scene_id: int = Field(ge=1)
    purpose: str = ""
    shot_type: ShotType = ShotType.MEDIUM
    camera_angle: CameraAngle = CameraAngle.EYE_LEVEL
    lens: Lens = Lens.MM50
    composition: Composition = Composition.RULE_OF_THIRDS
    blocking: Blocking = Field(default_factory=Blocking)
    lighting: LightingSetup = LightingSetup.KEY
    lighting_detail: str = ""
    action: str = ""
    motion_hint: str = ""
    emotion: str = ""

    @property
    def camera(self) -> str:
        """Shot size, angle and lens as one camera instruction."""
        return f"{self.shot_type.value}, {self.camera_angle.value}, {self.lens.value}"


class CinematicDirection(BaseModel):
    """The director's decisions for a whole film."""

    model_config = ConfigDict(frozen=True)

    title: str = ""
    scenes: tuple[SceneDirection, ...] = ()
    shots: tuple[ShotDirection, ...] = ()

    def scene(self, scene_id: int) -> SceneDirection | None:
        """The direction for ``scene_id``, if there is one."""
        return next((s for s in self.scenes if s.scene_id == scene_id), None)

    def shot(self, shot_id: int) -> ShotDirection | None:
        """The direction for ``shot_id``, if there is one."""
        return next((s for s in self.shots if s.shot_id == shot_id), None)
