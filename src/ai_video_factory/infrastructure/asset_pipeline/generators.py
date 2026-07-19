"""Asset generator contracts (structural Protocols).

Each generator produces one kind of asset and returns a uniform ``AssetResult``.
Image and speech have working adapters (see :mod:`.adapters`) that delegate to
the existing provider layers; subtitle and video are contracts only until their
own sprints implement them.
"""

from __future__ import annotations

from typing import Protocol

from ai_video_factory.domain.value_objects.chapter import StoryChapter
from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.infrastructure.asset_pipeline.models import AssetResult


class ImageGenerator(Protocol):
    """Generates the image assets for a set of image prompts."""

    async def generate_images(self, image_prompts: list[ImagePrompt]) -> AssetResult: ...


class SpeechGenerator(Protocol):
    """Generates the narration audio asset from a chapter."""

    async def generate_voice(self, chapter: StoryChapter) -> AssetResult: ...


class SubtitleGenerator(Protocol):
    """Generates the subtitle asset from a chapter (future sprint)."""

    async def generate_subtitles(self, chapter: StoryChapter) -> AssetResult: ...


class VideoComposer(Protocol):
    """Composes the final video asset from images, voice, and subtitles (future sprint)."""

    async def compose_video(
        self, images: AssetResult, voice: AssetResult, subtitles: AssetResult
    ) -> AssetResult: ...
