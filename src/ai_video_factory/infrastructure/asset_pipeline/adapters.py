"""Asset generator adapters that wrap the existing provider layers.

These make image and voice generation real by delegating to the Sprint-008
image provider and Sprint-010 speech provider — no business logic is
duplicated; each adapter only maps inputs and returns a uniform ``AssetResult``.
"""

from __future__ import annotations

from ai_video_factory.domain.value_objects.chapter import StoryChapter
from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.infrastructure.asset_pipeline.models import AssetResult
from ai_video_factory.infrastructure.media.image_storage import ImageStorage
from ai_video_factory.infrastructure.providers.image.base.models import ImageGenerationRequest
from ai_video_factory.infrastructure.providers.image.base.provider import ImageProvider
from ai_video_factory.infrastructure.providers.speech.base.models import SpeechSynthesisRequest
from ai_video_factory.infrastructure.providers.speech.base.provider import SpeechProvider


class ImageAssetGenerator:
    """Generates every image for a set of prompts via an :class:`ImageProvider`."""

    def __init__(self, provider: ImageProvider, storage: ImageStorage) -> None:
        self._provider = provider
        self._storage = storage

    async def generate_images(self, image_prompts: list[ImagePrompt]) -> AssetResult:
        paths: list[str] = []
        for prompt in image_prompts:
            request = ImageGenerationRequest(
                prompt=prompt.prompt,
                negative_prompt=prompt.negative_prompt,
                aspect_ratio=prompt.aspect_ratio,
                seed=prompt.seed,
                style=prompt.style,
            )
            response = await self._provider.generate(request)
            paths.append(str(response.image_path))
        return AssetResult(
            success=True,
            path=self._storage.directory,
            duration=0.0,
            metadata={"count": len(paths), "images": paths},
        )


class SpeechAssetGenerator:
    """Generates the narration audio for a chapter via a :class:`SpeechProvider`."""

    def __init__(self, provider: SpeechProvider) -> None:
        self._provider = provider

    async def generate_voice(self, chapter: StoryChapter) -> AssetResult:
        response = await self._provider.synthesize(SpeechSynthesisRequest(text=chapter.content))
        return AssetResult(
            success=True,
            path=response.audio_path,
            duration=response.duration_seconds,
            metadata={
                "voice": response.voice,
                "sample_rate": response.sample_rate,
                "provider": response.provider,
            },
        )
