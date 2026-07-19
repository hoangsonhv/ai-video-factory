"""Pipeline runner (infrastructure) — Phase 1: idea → outline → chapter → image prompts.

Composes the existing story generators; it contains no business logic of its
own. Stages run sequentially, each output is persisted immediately, and any
stage failure propagates (stopping the run) with earlier outputs already saved.
Progress is reported through an injected callback so the runner stays free of
any presentation concern.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ai_video_factory.domain.value_objects.idea import IdeaBrief
from ai_video_factory.infrastructure.config.settings import Settings
from ai_video_factory.infrastructure.pipeline.models import PipelineRequest, PipelineResult
from ai_video_factory.infrastructure.prompts.service import PromptService
from ai_video_factory.infrastructure.providers.factory.provider_factory import ProviderFactory
from ai_video_factory.infrastructure.story.chapter_generator import ChapterGenerator
from ai_video_factory.infrastructure.story.idea_generator import IdeaGenerator
from ai_video_factory.infrastructure.story.image_prompt_generator import ImagePromptGenerator
from ai_video_factory.infrastructure.story.outline_generator import OutlineGenerator
from ai_video_factory.infrastructure.story.writer import (
    write_chapter_json,
    write_ideas_json,
    write_image_prompts_json,
    write_outline_json,
)

StageCallback = Callable[[int, int, str], None]
_TOTAL_STAGES = 4


class PipelineRunner:
    """Runs the story pipeline through to image prompts (no image generation)."""

    def __init__(
        self,
        idea_generator: IdeaGenerator,
        outline_generator: OutlineGenerator,
        chapter_generator: ChapterGenerator,
        image_prompt_generator: ImagePromptGenerator,
        output_dir: Path,
    ) -> None:
        self._idea = idea_generator
        self._outline = outline_generator
        self._chapter = chapter_generator
        self._image_prompt = image_prompt_generator
        self._output_dir = output_dir

    @classmethod
    def from_settings(cls, settings: Settings) -> PipelineRunner:
        """Wire the runner from configuration, sharing one provider + prompt service."""
        provider = ProviderFactory.create(settings)
        prompts = PromptService.create(settings.prompts.root)
        return cls(
            IdeaGenerator(provider, prompts),
            OutlineGenerator(provider, prompts),
            ChapterGenerator(provider, prompts, debug_dir=settings.app.output_dir / "debug"),
            ImagePromptGenerator(provider, prompts),
            settings.app.output_dir,
        )

    async def run(
        self, request: PipelineRequest, *, on_stage: StageCallback | None = None
    ) -> PipelineResult:
        """Run all four stages, persisting each output before the next stage.

        Raises:
            AppError: If any stage fails; the run stops and earlier outputs remain.
        """
        self._report(on_stage, 1, "Generate ideas")
        brief = IdeaBrief(
            topic=request.topic,
            style=request.style,
            target_platform=request.target_platform,
            language=request.language,
        )
        ideas = await self._idea.generate(brief)
        ideas_path = self._output_dir / "ideas.json"
        write_ideas_json(ideas_path, brief, ideas)

        self._report(on_stage, 2, "Generate outline")
        outline = await self._outline.generate(
            ideas[0],
            target_duration=request.target_duration,
            chapter_count=request.chapter_count,
            language=request.language,
        )
        outline_path = self._output_dir / "story_outline.json"
        write_outline_json(outline_path, outline)

        self._report(on_stage, 3, "Generate chapter")
        chapter = await self._chapter.generate(outline, language=request.language)
        chapter_path = self._output_dir / "chapter.json"
        write_chapter_json(chapter_path, chapter)

        self._report(on_stage, 4, "Generate image prompts")
        image_prompts = await self._image_prompt.generate(
            chapter,
            style=request.style,
            count=request.image_count,
            language=request.language,
        )
        image_prompts_path = self._output_dir / "image_prompts.json"
        write_image_prompts_json(image_prompts_path, image_prompts)

        return PipelineResult(
            ideas=ideas,
            outline=outline,
            chapter=chapter,
            image_prompts=image_prompts,
            outputs=[ideas_path, outline_path, chapter_path, image_prompts_path],
        )

    @staticmethod
    def _report(on_stage: StageCallback | None, number: int, name: str) -> None:
        if on_stage is not None:
            on_stage(number, _TOTAL_STAGES, name)
