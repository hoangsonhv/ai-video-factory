"""Decide how each shot is filmed (pure, no I/O).

Given what a scene is for, this picks the size, angle, lens, composition,
blocking, light and action for every shot in it — the choices a director makes
standing on set, rather than the adjectives a prompt writer reaches for.

Coverage is varied deliberately: the size follows the scene's shape, the angle
follows the emotion, the lens follows the size, and consecutive shots are
pushed apart so a scene reads as coverage rather than one setup repeated.
"""

from __future__ import annotations

from ai_video_factory.domain.value_objects.cinema import (
    Blocking,
    SceneDirection,
    ShotDirection,
    ShotType,
)
from ai_video_factory.domain.value_objects.storyboard import Storyboard, StoryboardShot
from ai_video_factory.infrastructure.cinema.vocabulary import (
    activate,
    choose_angle,
    choose_composition,
    choose_lens,
    choose_lighting,
    choose_shot_type,
)

# How the frame should move, given the shot size.
_MOTION_BY_SHOT: dict[ShotType, str] = {
    ShotType.ESTABLISHING: "slow aerial drift revealing the space",
    ShotType.WIDE: "slow push in",
    ShotType.FULL_BODY: "tracking alongside the subject",
    ShotType.MEDIUM: "gentle handheld follow",
    ShotType.CLOSE_UP: "almost still, breathing with the subject",
    ShotType.EXTREME_CLOSE_UP: "micro push in, holding on the detail",
}

_POSITION_CYCLE: tuple[str, ...] = (
    "subject on the left third, facing into the frame",
    "subject centred, filling the frame",
    "subject on the right third, looking off-screen left",
    "subject low in frame beneath a tall space",
)


def _movement_path(action: str, shot_type: ShotType) -> str:
    """Where the subject travels across the frame during the shot."""
    lowered = action.lower()
    if any(word in lowered for word in ("run", "walk", "ride", "charge", "flee")):
        return "crossing frame left to right, camera holding the lead space"
    if any(word in lowered for word in ("fly", "rise", "ascend", "land")):
        return "rising through the frame, camera tilting to follow"
    if any(word in lowered for word in ("turn", "look back", "spin")):
        return "pivoting in place, eyeline swinging past camera"
    if shot_type in (ShotType.CLOSE_UP, ShotType.EXTREME_CLOSE_UP):
        return "held in place, only the expression changing"
    return "small step into the frame, settling on the mark"


class ShotDirector:
    """Decides the camera, composition, blocking, light and action per shot."""

    def direct(
        self, storyboard: Storyboard, scenes: tuple[SceneDirection, ...]
    ) -> tuple[ShotDirection, ...]:
        """Make every shot's decisions, varying coverage across the film."""
        by_scene = {scene.scene_id: scene for scene in scenes}
        counts: dict[int, int] = {}
        order_of_scene: dict[int, int] = {}
        for shot in storyboard.shots:
            counts[shot.scene_id] = counts.get(shot.scene_id, 0) + 1
            order_of_scene.setdefault(shot.scene_id, len(order_of_scene))

        directions: list[ShotDirection] = []
        # How many times each shot size has been used, so the lens alternates
        # within a size rather than by global position — otherwise close ups can
        # all land on the same parity and one lens quietly becomes the default.
        used: dict[ShotType, int] = {}
        for index, shot in enumerate(storyboard.shots):
            scene = by_scene.get(shot.scene_id)
            directions.append(
                self._direct_shot(
                    shot,
                    scene,
                    index,
                    counts[shot.scene_id],
                    order_of_scene[shot.scene_id],
                    used,
                )
            )
        return tuple(directions)

    @staticmethod
    def _direct_shot(
        shot: StoryboardShot,
        scene: SceneDirection | None,
        index: int,
        shot_count: int,
        scene_position: int,
        used: dict[ShotType, int],
    ) -> ShotDirection:
        emotion = shot.expression or (scene.emotion if scene else "")
        shot_type = choose_shot_type(
            shot.order, shot_count, is_scene_opening=shot.order == 1, scene_position=scene_position
        )
        angle = choose_angle(shot.order, emotion, shot_type, scene_position=scene_position)
        lens = choose_lens(shot_type, used.get(shot_type, 0))
        used[shot_type] = used.get(shot_type, 0) + 1
        composition = choose_composition(index, shot_type)
        action = activate(shot.action, index)

        return ShotDirection(
            shot_id=shot.id,
            scene_id=shot.scene_id,
            purpose=scene.purpose if scene else "",
            shot_type=shot_type,
            camera_angle=angle,
            lens=lens,
            composition=composition,
            blocking=Blocking(
                character_position=_POSITION_CYCLE[index % len(_POSITION_CYCLE)],
                object_position=shot.environment or "",
                movement_path=_movement_path(action, shot_type),
            ),
            lighting=choose_lighting(shot.lighting or shot.environment),
            lighting_detail=" ".join(shot.lighting.split()).strip(),
            action=action,
            motion_hint=_MOTION_BY_SHOT[shot_type],
            emotion=emotion,
        )
