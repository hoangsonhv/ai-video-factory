"""The Shot Planner (infrastructure service, pure decision-making).

Turns a storyboard into a validated shot plan: each shot gets a size, distance,
angle, lens, composition, visible body, camera move, focus, environment depth,
light, emotion, movement priority — and a reason it was chosen that way.

Two rules are enforced rather than hoped for:

- **the film's coverage is validated as a distribution** and re-planned
  automatically until it is inside its bounds;
- **a shot whose frame states nothing at any depth is rejected**, because that
  is precisely the shot that comes back as a portrait on a backdrop.

Deterministic and offline — the same storyboard always yields the same plan.
"""

from __future__ import annotations

from collections.abc import Mapping

from ai_video_factory.domain.value_objects.continuity import WorldBible
from ai_video_factory.domain.value_objects.director import DirectedMovie
from ai_video_factory.domain.value_objects.movie import Scene
from ai_video_factory.domain.value_objects.shot_plan import (
    PlannedShot,
    SceneKind,
    ShotPlan,
    ShotType,
)
from ai_video_factory.domain.value_objects.storyboard import Storyboard, StoryboardShot
from ai_video_factory.infrastructure.planner import framing
from ai_video_factory.infrastructure.planner.classifier import classify_scenes
from ai_video_factory.infrastructure.planner.distribution import Rebalance, measure, rebalance
from ai_video_factory.infrastructure.planner.environment import build_environment
from ai_video_factory.infrastructure.planner.errors import PlannerError

_PURPOSE_BY_KIND: dict[SceneKind, str] = {
    SceneKind.OPENING: "place the audience in the world before anything is asked of them",
    SceneKind.CONVERSATION: "carry the exchange between the characters",
    SceneKind.ACTION: "keep the movement and its geography readable",
    SceneKind.COMBAT: "keep both fighters and the ground between them visible",
    SceneKind.EMOTION: "hold on what the character is feeling",
    SceneKind.LANDSCAPE: "show the scale of the place the character is in",
}


class ShotPlanner:
    """Plans how every shot in a film is framed, and validates the whole."""

    def plan(
        self,
        storyboard: Storyboard,
        movie: DirectedMovie | None = None,
        world: WorldBible | None = None,
    ) -> ShotPlan:
        """Produce a validated shot plan for ``storyboard``.

        Raises:
            PlannerError: If the storyboard carries no shots, or a shot's frame
                states nothing in the foreground, midground or background.
        """
        if not storyboard.shots:
            raise PlannerError(
                "storyboard carries no shots; run `storyboard` before the shot planner"
            )
        world = world or WorldBible()
        scenes_by_id: Mapping[int, Scene] = (
            {scene.id: scene for scene in movie.scenes} if movie else {}
        )
        shots_by_scene = _group(storyboard.shots)
        kinds = self._kinds(scenes_by_id, shots_by_scene)

        sizes, kind_list, openings = self._initial_sizes(storyboard, kinds, shots_by_scene)
        balanced = rebalance(sizes, kind_list, openings)
        report = measure(balanced.sizes)

        shots = self._build(storyboard, scenes_by_id, world, kinds, balanced)
        self._reject_empty_frames(shots)

        return ShotPlan(
            title=storyboard.title,
            shots=shots,
            scene_kinds=kinds,
            replans=len(balanced.notes),
            distribution=report,
            notes=tuple(balanced.notes),
        )

    @staticmethod
    def _kinds(
        scenes_by_id: Mapping[int, Scene],
        shots_by_scene: dict[int, tuple[StoryboardShot, ...]],
    ) -> dict[int, SceneKind]:
        """Name every scene, using the movie when it is available.

        A storyboard alone carries no dialogue, so without the directed movie a
        scene can never be classified as a conversation. The plan is still
        valid — it simply cannot know what it was never told.
        """
        ordered_ids = sorted(shots_by_scene)
        scenes = tuple(
            scenes_by_id.get(scene_id) or Scene(id=scene_id, duration=1) for scene_id in ordered_ids
        )
        return classify_scenes(scenes, shots_by_scene)

    @staticmethod
    def _initial_sizes(
        storyboard: Storyboard,
        kinds: dict[int, SceneKind],
        shots_by_scene: dict[int, tuple[StoryboardShot, ...]],
    ) -> tuple[list[ShotType], list[SceneKind], list[bool]]:
        """The size each shot's own content asks for, before validation."""
        sizes: list[ShotType] = []
        kind_list: list[SceneKind] = []
        openings: list[bool] = []
        position: dict[int, int] = {}

        for shot in storyboard.shots:
            kind = kinds.get(shot.scene_id, SceneKind.ACTION)
            index = position.get(shot.scene_id, 0)
            position[shot.scene_id] = index + 1
            is_opening = index == 0
            sizes.append(
                framing.coverage_for(
                    kind,
                    index,
                    len(shots_by_scene.get(shot.scene_id, ())),
                    is_scene_opening=is_opening,
                )
            )
            kind_list.append(kind)
            openings.append(is_opening)
        return sizes, kind_list, openings

    @staticmethod
    def _build(
        storyboard: Storyboard,
        scenes_by_id: Mapping[int, Scene],
        world: WorldBible,
        kinds: dict[int, SceneKind],
        balanced: Rebalance,
    ) -> tuple[PlannedShot, ...]:
        """Turn each chosen size into every other framing decision."""
        used: dict[ShotType, int] = {}
        planned: list[PlannedShot] = []

        for index, (shot, shot_type) in enumerate(
            zip(storyboard.shots, balanced.sizes, strict=True)
        ):
            scene = scenes_by_id.get(shot.scene_id)
            kind = kinds.get(shot.scene_id, SceneKind.ACTION)
            emotion = shot.expression or (scene.emotion if scene else "")
            lens = framing.lens_for(shot_type, used.get(shot_type, 0))
            used[shot_type] = used.get(shot_type, 0) + 1

            planned.append(
                PlannedShot(
                    shot_id=shot.id,
                    scene_id=shot.scene_id,
                    purpose=_PURPOSE_BY_KIND[kind],
                    shot_type=shot_type,
                    camera_distance=framing.distance_for(shot_type),
                    camera_angle=framing.angle_for(emotion, shot_type, index),
                    lens=lens,
                    composition=framing.composition_for(shot_type, index),
                    visible_body=framing.body_for(shot_type),
                    camera_motion=framing.motion_for(shot_type, shot.camera_motion),
                    focus_subject=_focus(shot, scene),
                    environment_visibility=build_environment(shot, scene, world, shot_type),
                    lighting_style=framing.lighting_for(f"{shot.lighting} {shot.environment}"),
                    emotion=" ".join(emotion.split()).strip(),
                    movement_priority=framing.priority_for(
                        shot.action, shot.camera_motion, shot.environment
                    ),
                    reason=_reason(kind, shot_type, index in balanced.changed),
                )
            )
        return tuple(planned)

    @staticmethod
    def _reject_empty_frames(shots: tuple[PlannedShot, ...]) -> None:
        """Refuse a plan containing a frame that states nothing at any depth."""
        empty = [shot.shot_id for shot in shots if shot.environment_visibility.is_empty]
        if empty:
            raise PlannerError(
                "shots state nothing in the foreground, midground or background; "
                "they would render as portraits on a blank backdrop",
                context={"shots": empty},
            )


def _group(shots: tuple[StoryboardShot, ...]) -> dict[int, tuple[StoryboardShot, ...]]:
    grouped: dict[int, list[StoryboardShot]] = {}
    for shot in shots:
        grouped.setdefault(shot.scene_id, []).append(shot)
    return {scene_id: tuple(members) for scene_id, members in grouped.items()}


def _focus(shot: StoryboardShot, scene: Scene | None) -> str:
    """What the frame is actually about — the character, doing the action."""
    subject = shot.character or (scene.characters[0] if scene and scene.characters else "")
    action = " ".join(shot.action.split()).strip()
    subject = subject.replace("_", " ").strip()
    if subject and action:
        return f"{subject} {action}"
    return action or subject


def _reason(kind: SceneKind, shot_type: ShotType, was_rebalanced: bool) -> str:
    """Why this size was chosen — content, or the distribution overriding it."""
    base = f"{kind.value} scene covered as {shot_type.value}"
    if was_rebalanced:
        return f"{base}; adjusted to keep the film's coverage inside its bounds"
    return base
