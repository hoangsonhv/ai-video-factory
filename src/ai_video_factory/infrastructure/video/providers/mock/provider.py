"""``MockVideoProvider`` — the development video provider.

Satisfies the :class:`VideoProvider` contract without calling any AI service:
it renders each scene locally with the existing ffmpeg pipeline, writing
``output/video_clips/scene_001.mp4``, ``scene_002.mp4``, … This exists so the
rest of the system can be built and tested against the abstraction while no
commercial video provider is integrated. **Development only** — it generates
slideshow clips, not AI video.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from ai_video_factory.errors import MediaError
from ai_video_factory.infrastructure.config.settings import VideoProviderSettings, VideoSettings
from ai_video_factory.infrastructure.diagnostics import check_ffmpeg
from ai_video_factory.infrastructure.providers.base.models import ProviderHealth
from ai_video_factory.infrastructure.video.ffmpeg_composer import (
    FfmpegRunner,
    default_ffmpeg_runner,
)
from ai_video_factory.infrastructure.video.providers.base.models import (
    ClipReferences,
    VideoGenerationRequest,
    VideoGenerationResult,
    VideoJobStatus,
)
from ai_video_factory.infrastructure.video.providers.errors import VideoProviderError
from ai_video_factory.infrastructure.video.providers.mock.clip_command import build_clip_command
from ai_video_factory.shared.health import HealthStatus

_logger = logging.getLogger(__name__)

PROVIDER_NAME = "mock"
DEFAULT_MODEL = "mock-slideshow"


def clip_filename(clip_id: int) -> str:
    """The clip filename for ``clip_id`` (``shot_001.mp4``)."""
    return f"shot_{clip_id:03d}.mp4"


class MockVideoProvider:
    """Renders scene clips locally with ffmpeg — for development only."""

    def __init__(
        self,
        settings: VideoProviderSettings,
        video_settings: VideoSettings,
        output_dir: Path,
        *,
        runner: FfmpegRunner | None = None,
    ) -> None:
        self._settings = settings
        self._video_settings = video_settings
        self._output_dir = output_dir
        # Resolved at construction (not as a default argument) so the runner
        # stays injectable and patchable in tests.
        self._runner = runner if runner is not None else default_ffmpeg_runner

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    def supported_models(self) -> list[str]:
        return [DEFAULT_MODEL]

    async def health_check(self) -> ProviderHealth:
        """The mock renders locally, so its health is ffmpeg's availability."""
        ffmpeg = check_ffmpeg()
        if ffmpeg.is_failure:
            return ProviderHealth(
                status=HealthStatus.FAIL,
                detail=f"mock provider needs ffmpeg: {ffmpeg.detail}",
            )
        return ProviderHealth(
            status=HealthStatus.WARN,
            detail="development provider: renders slideshow clips, not AI video",
        )

    async def generate(
        self,
        request: VideoGenerationRequest,
        references: ClipReferences | None = None,
    ) -> VideoGenerationResult:
        """Render the clip for ``request``.

        Raises:
            VideoProviderError: If ffmpeg is unavailable, times out, or fails
                every attempt.
        """
        output_path = self._output_dir / clip_filename(request.clip_id)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image = self._reference_image(request, references)
        command = build_clip_command(
            output_path=output_path,
            duration=request.duration,
            settings=self._video_settings,
            reference_image=image,
        )
        await self._run_with_retry(command, request.scene_id)

        return VideoGenerationResult(
            scene_id=request.scene_id,
            clip_id=request.clip_id,
            shot_ids=request.shot_ids,
            provider=PROVIDER_NAME,
            model=self._settings.model,
            status=VideoJobStatus.COMPLETED,
            remote_job_id=None,
            video_path=output_path,
            preview_path=None,
            duration=request.duration,
            metadata={
                "resolution": f"{self._video_settings.width}x{self._video_settings.height}",
                "fps": self._video_settings.fps,
                "source": "reference_image" if image else "color",
                "mock": True,
            },
        )

    @staticmethod
    def _reference_image(
        request: VideoGenerationRequest, references: ClipReferences | None = None
    ) -> Path | None:
        """The still to animate: the offered reference, else the request's own."""
        if references is not None:
            primary = references.primary
            if primary is not None and primary.is_file():
                return primary
        return next((image for image in request.reference_images if image.is_file()), None)

    async def _run_with_retry(self, command: list[str], scene_id: int) -> None:
        attempts = self._settings.retry_count + 1
        return_code = 0
        stderr = ""
        for attempt in range(1, attempts + 1):
            try:
                return_code, stderr = await asyncio.wait_for(
                    asyncio.to_thread(self._runner, command), timeout=self._settings.timeout
                )
            except TimeoutError as exc:
                raise VideoProviderError(
                    f"scene {scene_id}: rendering timed out after {self._settings.timeout}s",
                    retryable=True,
                    context={"scene": scene_id},
                ) from exc
            except MediaError as exc:  # missing ffmpeg binary — terminal
                raise VideoProviderError(str(exc), context={"scene": scene_id}) from exc
            if return_code == 0:
                return
            _logger.warning(
                "mock video attempt %d/%d failed for scene %d (code %d)",
                attempt,
                attempts,
                scene_id,
                return_code,
            )
        raise VideoProviderError(
            f"scene {scene_id}: ffmpeg failed after {attempts} attempt(s) (exit {return_code})",
            context={"scene": scene_id, "stderr": stderr[-1500:]},
        )
