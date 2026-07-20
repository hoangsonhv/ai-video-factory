"""Kling AI implementation of the :class:`VideoProvider` protocol.

Image-to-video: each scene's generated image plus its ``video_prompt`` become
one clip. Kling is asynchronous, so a generation is four steps — submit, poll,
download, save — exposed individually (:meth:`submit_job`, :meth:`poll_job`,
:meth:`download_result`, :meth:`cancel_job`) and composed by :meth:`generate`.

Transient failures (429/503/timeout) are retried with exponential backoff by
the shared :class:`RetryPolicy`; terminal failures (bad credentials, malformed
response) are not. A job that outlives ``poll_timeout`` is cancelled rather
than left running and billing. HTTP specifics live in :mod:`.client`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from ai_video_factory.infrastructure.config.settings import VideoProviderSettings
from ai_video_factory.infrastructure.providers.base.errors import AIProviderError
from ai_video_factory.infrastructure.providers.base.errors import (
    TimeoutError as ProviderTimeoutError,
)
from ai_video_factory.infrastructure.providers.base.models import ProviderHealth
from ai_video_factory.infrastructure.providers.base.retry import RetryPolicy
from ai_video_factory.infrastructure.video.providers.base.models import (
    ClipReferences,
    VideoGenerationRequest,
    VideoGenerationResult,
    VideoJobStatus,
)
from ai_video_factory.infrastructure.video.providers.errors import VideoProviderError
from ai_video_factory.infrastructure.video.providers.kling.client import (
    KlingClient,
    RealKlingClient,
)
from ai_video_factory.infrastructure.video.providers.kling.models import KlingJob
from ai_video_factory.infrastructure.video.providers.mock.provider import clip_filename
from ai_video_factory.shared.health import HealthStatus

_logger = logging.getLogger(__name__)

PROVIDER_NAME = "kling"
DEFAULT_MODEL = "kling-v1"
SUPPORTED_MODELS = ("kling-v1", "kling-v1-5", "kling-v1-6", "kling-v2-master")

# Reported back to the CLI so it can drive the progress bar.
PHASE_SUBMITTING = "submitting"
PHASE_WAITING = "waiting"
PHASE_DOWNLOADING = "downloading"
PHASE_COMPLETED = "completed"

ProgressCallback = Callable[[int, str], None]
"""Invoked with ``(scene_id, phase)`` as a generation moves between phases."""


class KlingVideoProvider:
    """AI video provider backed by Kling's image-to-video API."""

    def __init__(
        self,
        settings: VideoProviderSettings,
        output_dir: Path,
        *,
        client: KlingClient | None = None,
        on_progress: ProgressCallback | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._settings = settings
        self._output_dir = output_dir
        self._on_progress = on_progress
        self._clock = clock
        self._sleep = sleep if sleep is not None else asyncio.sleep
        self._retry = RetryPolicy(max_retries=settings.retry_count)
        self._client = client if client is not None else self._build_client(settings)

    @staticmethod
    def _build_client(settings: VideoProviderSettings) -> KlingClient | None:
        """Build the HTTP client, or ``None`` when no API key is configured."""
        if settings.api_key is None:
            return None
        return RealKlingClient(
            api_key=settings.api_key.get_secret_value(),
            base_url=settings.base_url,
            timeout=settings.timeout,
        )

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    def supported_models(self) -> list[str]:
        return list(SUPPORTED_MODELS)

    async def health_check(self) -> ProviderHealth:
        """Report configuration readiness without spending a generation."""
        if self._client is None:
            return ProviderHealth(
                status=HealthStatus.FAIL,
                detail="no API key configured (set AIVF_VIDEO_PROVIDER__API_KEY)",
            )
        if self._settings.model not in SUPPORTED_MODELS:
            return ProviderHealth(
                status=HealthStatus.WARN,
                detail=(
                    f"model {self._settings.model!r} is not a known Kling model; "
                    f"known: {', '.join(SUPPORTED_MODELS)}"
                ),
            )
        return ProviderHealth(
            status=HealthStatus.OK,
            detail=f"configured (model={self._settings.model}, base={self._settings.base_url})",
        )

    # --- job lifecycle -----------------------------------------------------

    async def submit_job(
        self, request: VideoGenerationRequest, references: ClipReferences | None = None
    ) -> KlingJob:
        """Submit ``request`` as an image-to-video job and return the task.

        Raises:
            VideoProviderError: If no image is available, the provider is
                unconfigured, or the submission fails.
        """
        client = self._require_client()
        image = self._reference_image(request, references)
        self._report(request.scene_id, PHASE_SUBMITTING)
        job = await self._call(
            lambda: client.submit_image_to_video(request, model=self._settings.model, image=image),
            scene_id=request.scene_id,
            action="submit",
        )
        _logger.info("kling job submitted | scene=%d | task=%s", request.scene_id, job.task_id)
        return job

    async def poll_job(self, task_id: str, *, scene_id: int = 1) -> KlingJob:
        """Poll ``task_id`` until it finishes, fails, or exceeds the timeout.

        Raises:
            VideoProviderError: If the job fails or outlives ``poll_timeout``
                (in which case cancellation is attempted).
        """
        client = self._require_client()
        deadline = self._clock() + self._settings.poll_timeout
        self._report(scene_id, PHASE_WAITING)
        while True:
            job = await self._call(
                lambda: client.get_job(task_id), scene_id=scene_id, action="poll"
            )
            if job.status is VideoJobStatus.COMPLETED:
                return job
            if job.status is VideoJobStatus.FAILED:
                raise VideoProviderError(
                    f"scene {scene_id}: Kling job {task_id} failed: {job.message or 'no detail'}",
                    context={"scene": scene_id, "task_id": task_id},
                )
            if self._clock() >= deadline:
                await self._cancel_quietly(task_id, scene_id)
                raise VideoProviderError(
                    f"scene {scene_id}: Kling job {task_id} did not finish within "
                    f"{self._settings.poll_timeout}s (cancelled)",
                    retryable=True,
                    context={"scene": scene_id, "task_id": task_id},
                )
            await self._sleep(self._settings.poll_interval)

    async def download_result(self, job: KlingJob, *, clip_id: int = 1, scene_id: int = 1) -> Path:
        """Download the finished clip to ``output/video_clips/scene_NNN.mp4``.

        Raises:
            VideoProviderError: If the job carries no video URL or the download
                fails.
        """
        client = self._require_client()
        if not job.video_url:
            raise VideoProviderError(
                f"scene {scene_id}: Kling job {job.task_id} completed without a video URL",
                context={"scene": scene_id, "task_id": job.task_id},
            )
        self._report(scene_id, PHASE_DOWNLOADING)
        url = job.video_url
        data = await self._call(lambda: client.download(url), scene_id=scene_id, action="download")
        path = self._output_dir / clip_filename(clip_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    async def cancel_job(self, task_id: str, *, scene_id: int = 1) -> None:
        """Cancel a running job.

        Raises:
            VideoProviderError: If the cancellation call fails.
        """
        client = self._require_client()
        await self._call(lambda: client.cancel_job(task_id), scene_id=scene_id, action="cancel")
        _logger.info("kling job cancelled | scene=%d | task=%s", scene_id, task_id)

    # --- the VideoProvider contract ----------------------------------------

    async def generate(
        self,
        request: VideoGenerationRequest,
        references: ClipReferences | None = None,
    ) -> VideoGenerationResult:
        """Submit, poll, download and save the clip for ``request``.

        Raises:
            VideoProviderError: On any provider-side failure (translated).
        """
        job = await self.submit_job(request, references)
        finished = await self.poll_job(job.task_id, scene_id=request.scene_id)
        path = await self.download_result(
            finished, clip_id=request.clip_id, scene_id=request.scene_id
        )
        self._report(request.scene_id, PHASE_COMPLETED)

        duration = finished.duration or request.duration
        return VideoGenerationResult(
            scene_id=request.scene_id,
            clip_id=request.clip_id,
            shot_ids=request.shot_ids,
            provider=PROVIDER_NAME,
            model=self._settings.model,
            status=VideoJobStatus.COMPLETED,
            remote_job_id=finished.task_id,
            video_path=path,
            preview_path=None,
            duration=duration,
            metadata={
                "aspect_ratio": request.aspect_ratio,
                "cost": self.estimate_cost(duration),
                "base_url": self._settings.base_url,
            },
        )

    def estimate_cost(self, duration: float) -> float:
        """Estimated spend for ``duration`` seconds.

        Kling does not return a price, so this is derived from the configured
        ``cost_per_second`` and is ``0.0`` (meaning *unknown*) until an
        operator sets that rate.
        """
        return round(duration * self._settings.cost_per_second, 4)

    # --- internals ---------------------------------------------------------

    def _require_client(self) -> KlingClient:
        if self._client is None:
            raise VideoProviderError(
                "Kling is not configured: set AIVF_VIDEO_PROVIDER__API_KEY (KLING_API_KEY)"
            )
        return self._client

    @staticmethod
    def _reference_image(
        request: VideoGenerationRequest, references: ClipReferences | None = None
    ) -> Path:
        offered = references.primary if references is not None else None
        image = (
            offered
            if offered is not None and offered.is_file()
            else next((path for path in request.reference_images if path.is_file()), None)
        )
        if image is None:
            raise VideoProviderError(
                f"scene {request.scene_id}: Kling image-to-video needs a reference image; "
                "generate the scene images first",
                context={"scene": request.scene_id},
            )
        return image

    def _report(self, scene_id: int, phase: str) -> None:
        if self._on_progress is not None:
            self._on_progress(scene_id, phase)

    async def _call[T](
        self, operation: Callable[[], Awaitable[T]], *, scene_id: int, action: str
    ) -> T:
        """Run one client call with retry + per-request timeout, translating errors."""

        async def _once() -> T:
            try:
                return await asyncio.wait_for(operation(), timeout=self._settings.timeout)
            except TimeoutError as exc:
                raise ProviderTimeoutError(
                    f"Kling {action} timed out after {self._settings.timeout}s"
                ) from exc

        try:
            return await self._retry.run(_once)
        except AIProviderError as exc:
            raise VideoProviderError(
                f"scene {scene_id}: Kling {action} failed: {exc}",
                retryable=exc.retryable,
                context={"scene": scene_id, "action": action},
            ) from exc

    async def _cancel_quietly(self, task_id: str, scene_id: int) -> None:
        """Best-effort cancellation — never masks the error that triggered it."""
        try:
            await self.cancel_job(task_id, scene_id=scene_id)
        except VideoProviderError as exc:
            _logger.warning("kling cancel failed | task=%s | %s", task_id, exc)
