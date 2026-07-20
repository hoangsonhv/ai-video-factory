"""The shot planning stage end to end (infrastructure service).

Plans every frame, composes the image prompts from that plan, enforces the
portrait guard, and counts the result.

Deterministic and offline: no provider is contacted, and no video or compose
stage is touched.
"""

from __future__ import annotations

from ai_video_factory.domain.value_objects.continuity import CharacterBible, WorldBible
from ai_video_factory.domain.value_objects.director import DirectedMovie
from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.domain.value_objects.shot_plan import PlannedShot, ShotPlan, ShotStatistics
from ai_video_factory.domain.value_objects.storyboard import Storyboard, StoryboardShot
from ai_video_factory.infrastructure.continuity.prompt_composer import (
    PromptSource,
    build_prompt,
    find_violations,
    strip_framing,
)
from ai_video_factory.infrastructure.planner.errors import PlannerError
from ai_video_factory.infrastructure.planner.planner import ShotPlanner
from ai_video_factory.infrastructure.planner.statistics import build_statistics


class PlanResult:
    """Everything one run of the stage produced."""

    def __init__(
        self,
        plan: ShotPlan,
        prompts: tuple[ImagePrompt, ...],
        statistics: ShotStatistics,
        sanitized: tuple[int, ...],
    ) -> None:
        self.plan = plan
        self.prompts = prompts
        self.statistics = statistics
        self.sanitized = sanitized
        """Shots whose source text carried framing language the plan overruled."""


class ShotPlanningEngine:
    """Plans the film's framing and rebuilds every image prompt from it."""

    def __init__(self, planner: ShotPlanner | None = None) -> None:
        self._planner = planner or ShotPlanner()

    def run(
        self,
        storyboard: Storyboard,
        bible: CharacterBible,
        world: WorldBible,
        movie: DirectedMovie | None = None,
        *,
        aspect_ratio: str = "9:16",
    ) -> PlanResult:
        """Plan every shot, then compose a prompt that obeys the plan.

        Raises:
            PlannerError: If a prompt still carries framing the plan never
                approved after its source text has been cleaned.
        """
        plan = self._planner.plan(storyboard, movie, world)
        shots_by_id = {shot.id: shot for shot in storyboard.shots}

        prompts: list[ImagePrompt] = []
        sanitized: list[int] = []
        violations: dict[int, tuple[str, ...]] = {}

        for planned in plan.shots:
            source = shots_by_id.get(planned.shot_id)
            cleaned, was_sanitized = self._clean_source(planned, source)
            if was_sanitized:
                sanitized.append(planned.shot_id)

            prompt = build_prompt(self._source(cleaned, source), bible, world)
            found = find_violations(prompt, allowed=cleaned.is_close)
            if found:
                violations[planned.shot_id] = found
            prompts.append(
                self._image_prompt(cleaned, prompt, world, source, aspect_ratio=aspect_ratio)
            )

        if violations:
            raise PlannerError(
                "prompts carry close-up framing the shot plan never approved",
                context={"shots": {str(k): list(v) for k, v in violations.items()}},
            )

        return PlanResult(
            plan=plan,
            prompts=tuple(prompts),
            statistics=build_statistics(plan),
            sanitized=tuple(sanitized),
        )

    @staticmethod
    def _clean_source(
        planned: PlannedShot, source: StoryboardShot | None
    ) -> tuple[PlannedShot, bool]:
        """Strip framing language the plan did not approve from the shot's text.

        The storyboard's own words are the leak: an LLM wrote "close-up" into
        the action and environment. Removing it there — rather than refusing
        the shot — keeps what the writer meant while letting the plan decide
        the frame.
        """
        del source  # the planned shot already carries the text that reaches a prompt
        focus = strip_framing(planned.focus_subject, allowed=planned.is_close)
        visibility = planned.environment_visibility
        environment = visibility.model_copy(
            update={
                "foreground": strip_framing(visibility.foreground, allowed=planned.is_close),
                "midground": strip_framing(visibility.midground, allowed=planned.is_close),
                "background": strip_framing(visibility.background, allowed=planned.is_close),
            }
        )
        changed = focus != planned.focus_subject or environment != visibility
        if not changed:
            return planned, False
        return (
            planned.model_copy(
                update={"focus_subject": focus, "environment_visibility": environment}
            ),
            True,
        )

    @staticmethod
    def _source(planned: PlannedShot, shot: StoryboardShot | None) -> PromptSource:
        """Adapt a planned shot into what the prompt builder asks for.

        The action is the storyboard's; the camera is the plan's. That split is
        deliberate: the storyboard says what happens, the plan says how it is
        filmed — and letting the storyboard choose the framing is what produced
        a film of portraits.
        """
        visibility = planned.environment_visibility
        return PromptSource(
            character_id=shot.character if shot else "",
            emotion=planned.emotion,
            action=shot.action if shot else planned.focus_subject,
            # The three depths go in as three fields, never as the summary
            # plus its own parts — that wrote each of them into the prompt twice.
            environment=visibility.background,
            weather=visibility.foreground,
            objects=visibility.midground,
            camera=planned.camera,
            camera_movement=planned.camera_motion,
            lighting=planned.lighting_style.value,
            composition=planned.composition.value,
            allows_close_framing=planned.is_close,
        )

    @staticmethod
    def _image_prompt(
        planned: PlannedShot,
        prompt: str,
        world: WorldBible,
        source: StoryboardShot | None,
        *,
        aspect_ratio: str,
    ) -> ImagePrompt:
        """Wrap the composed text in the existing image-prompt shape."""
        return ImagePrompt(
            scene_number=planned.shot_id,
            prompt=prompt,
            negative_prompt=world.negative_prompt,
            aspect_ratio=aspect_ratio,
            style=world.style,
            camera=planned.camera,
            lighting=planned.lighting_style.value,
            character_reference=source.character if source else "",
            environment=planned.environment_visibility.summary,
        )
