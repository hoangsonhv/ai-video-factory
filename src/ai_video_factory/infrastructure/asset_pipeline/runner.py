"""Asset pipeline runner (infrastructure).

Orchestrates the four asset stages (images → voice → subtitles → video) over
injected generators. Image and voice are wired to real adapters; subtitle and
video have no generator yet, so those stages raise a clear
:class:`AssetStageUnavailableError` until their sprints wire them in.
"""

from __future__ import annotations

from ai_video_factory.domain.value_objects.chapter import StoryChapter
from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.infrastructure.asset_pipeline.adapters import (
    ImageAssetGenerator,
    SpeechAssetGenerator,
)
from ai_video_factory.infrastructure.asset_pipeline.errors import AssetStageUnavailableError
from ai_video_factory.infrastructure.asset_pipeline.generators import (
    ImageGenerator,
    SpeechGenerator,
    SubtitleGenerator,
    VideoComposer,
)
from ai_video_factory.infrastructure.asset_pipeline.models import AssetResult, AssetStage
from ai_video_factory.infrastructure.config.settings import Settings
from ai_video_factory.infrastructure.media.audio_storage import AudioStorage
from ai_video_factory.infrastructure.media.image_storage import ImageStorage
from ai_video_factory.infrastructure.providers.image.factory.image_provider_factory import (
    ImageProviderFactory,
)
from ai_video_factory.infrastructure.providers.speech.factory.speech_provider_factory import (
    SpeechProviderFactory,
)

_PENDING = "—"


class AssetPipelineRunner:
    """Runs the asset stages over injected generators."""

    def __init__(
        self,
        image_generator: ImageGenerator,
        speech_generator: SpeechGenerator,
        subtitle_generator: SubtitleGenerator | None = None,
        video_composer: VideoComposer | None = None,
    ) -> None:
        self._image = image_generator
        self._speech = speech_generator
        self._subtitle = subtitle_generator
        self._video = video_composer

    @classmethod
    def from_settings(cls, settings: Settings) -> AssetPipelineRunner:
        """Wire the runner from configuration (image + voice ready; subtitle/video pending)."""
        image_storage = ImageStorage(settings.app.output_dir / "images")
        audio_storage = AudioStorage(settings.app.output_dir / "audio")
        image_provider = ImageProviderFactory.create(settings, image_storage)
        speech_provider = SpeechProviderFactory.create(settings, audio_storage)
        return cls(
            ImageAssetGenerator(image_provider, image_storage),
            SpeechAssetGenerator(speech_provider),
        )

    async def generate_images(self, image_prompts: list[ImagePrompt]) -> AssetResult:
        """Generate every image asset."""
        return await self._image.generate_images(image_prompts)

    async def generate_voice(self, chapter: StoryChapter) -> AssetResult:
        """Generate the narration audio asset."""
        return await self._speech.generate_voice(chapter)

    async def generate_subtitles(self, chapter: StoryChapter) -> AssetResult:
        """Generate the subtitle asset (raises until a generator is wired)."""
        if self._subtitle is None:
            raise AssetStageUnavailableError("subtitle generation is not available yet")
        return await self._subtitle.generate_subtitles(chapter)

    async def compose_video(
        self, images: AssetResult, voice: AssetResult, subtitles: AssetResult
    ) -> AssetResult:
        """Compose the final video asset (raises until a composer is wired)."""
        if self._video is None:
            raise AssetStageUnavailableError("video composition is not available yet")
        return await self._video.compose_video(images, voice, subtitles)

    def stage_status(self) -> list[AssetStage]:
        """Report the readiness of each pipeline stage."""
        return [
            AssetStage(name="images", backend=type(self._image).__name__, ready=True),
            AssetStage(name="voice", backend=type(self._speech).__name__, ready=True),
            AssetStage(
                name="subtitles",
                backend=type(self._subtitle).__name__ if self._subtitle else _PENDING,
                ready=self._subtitle is not None,
            ),
            AssetStage(
                name="video",
                backend=type(self._video).__name__ if self._video else _PENDING,
                ready=self._video is not None,
            ),
        ]
