"""The Cinematic Director (infrastructure service).

Runs the two directors over a storyboard — :class:`SceneDirector` for what each
scene is for, :class:`ShotDirector` for how each shot is filmed — and rebuilds
every image prompt from those decisions.

Deterministic and offline: the same storyboard always yields the same coverage.
No provider is contacted, and no video or compose stage is touched.
"""

from __future__ import annotations

from ai_video_factory.domain.value_objects.cinema import (
    CinematicDirection,
    ShotDirection,
    ShotType,
)
from ai_video_factory.domain.value_objects.continuity import (
    CharacterBible,
    VisualContext,
    WorldBible,
)
from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.domain.value_objects.storyboard import Storyboard
from ai_video_factory.infrastructure.cinema.errors import CinemaError
from ai_video_factory.infrastructure.cinema.scene_director import SceneDirector
from ai_video_factory.infrastructure.cinema.shot_director import ShotDirector
from ai_video_factory.infrastructure.continuity.context import build_visual_context
from ai_video_factory.infrastructure.continuity.prompt_composer import (
    PromptSource,
    build_prompt,
)


class CinemaResult:
    """Everything one run produced."""

    def __init__(self, direction: CinematicDirection, prompts: tuple[ImagePrompt, ...]) -> None:
        self.direction = direction
        self.prompts = prompts


class CinematicDirector:
    """Decides the coverage for a film and composes prompts that serve it."""

    def __init__(
        self,
        scene_director: SceneDirector | None = None,
        shot_director: ShotDirector | None = None,
    ) -> None:
        self._scenes = scene_director or SceneDirector()
        self._shots = shot_director or ShotDirector()

    def direct(self, storyboard: Storyboard) -> CinematicDirection:
        """Make every scene and shot decision for ``storyboard``.

        Raises:
            CinemaError: If the storyboard carries no shots.
        """
        if not storyboard.shots:
            raise CinemaError(
                "storyboard carries no shots; run `storyboard` before the cinematic director"
            )
        scenes = self._scenes.direct(storyboard)
        return CinematicDirection(
            title=storyboard.title,
            scenes=scenes,
            shots=self._shots.direct(storyboard, scenes),
        )

    def run(self, storyboard: Storyboard, bible: CharacterBible, world: WorldBible) -> CinemaResult:
        """Direct the film, then rebuild every prompt from those decisions."""
        direction = self.direct(storyboard)
        contexts = build_visual_context(storyboard, bible, world).shots

        prompts = tuple(
            ImagePrompt(
                scene_number=context.shot_id,
                prompt=build_prompt(
                    self._source(context, direction.shot(context.shot_id)), bible, world
                ),
                negative_prompt=world.negative_prompt,
                aspect_ratio="9:16",
                style=world.style,
                camera=self._camera_for(direction, context.shot_id),
                lighting=context.lighting_continuity,
                character_reference=context.character_state,
                environment=context.environment_continuity,
            )
            for context in contexts
        )
        return CinemaResult(direction=direction, prompts=prompts)

    @staticmethod
    def _source(context: VisualContext, shot: ShotDirection | None) -> PromptSource:
        """Adapt a visual context plus its direction into the builder's input."""
        current = context.current_shot
        return PromptSource(
            character_id=context.character_state,
            action=shot.action if shot else current.action,
            environment=context.environment_continuity or current.environment,
            camera=shot.camera if shot else current.camera,
            lighting=shot.lighting.value if shot else context.lighting_continuity,
            composition=shot.composition.value if shot else "",
            allows_close_framing=shot is not None
            and shot.shot_type in (ShotType.CLOSE_UP, ShotType.EXTREME_CLOSE_UP),
        )

    @staticmethod
    def _camera_for(direction: CinematicDirection, shot_id: int) -> str:
        shot = direction.shot(shot_id)
        return shot.camera if shot else ""
