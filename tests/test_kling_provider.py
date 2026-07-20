"""Tests for the Kling video provider (job lifecycle, retry, download)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import SecretStr

from ai_video_factory.infrastructure.config.settings import VideoProviderSettings
from ai_video_factory.infrastructure.providers.base.errors import (
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
)
from ai_video_factory.infrastructure.video.providers.base.models import (
    VideoGenerationRequest,
    VideoJobStatus,
)
from ai_video_factory.infrastructure.video.providers.errors import VideoProviderError
from ai_video_factory.infrastructure.video.providers.kling.models import KlingJob
from ai_video_factory.infrastructure.video.providers.kling.provider import (
    KlingVideoProvider,
)
from ai_video_factory.shared.health import HealthStatus


class _FakeClient:
    """A scripted KlingClient — records calls, replays queued outcomes."""

    def __init__(
        self,
        *,
        poll_results: list[KlingJob | Exception] | None = None,
        submit_result: KlingJob | Exception | None = None,
        download_result: bytes | Exception = b"mp4-bytes",
    ) -> None:
        self._poll_results = poll_results or [
            KlingJob(task_id="task-1", status=VideoJobStatus.COMPLETED, video_url="u", duration=5.0)
        ]
        self._submit_result = submit_result or KlingJob(
            task_id="task-1", status=VideoJobStatus.QUEUED
        )
        self._download_result = download_result
        self.submits = 0
        self.polls = 0
        self.downloads = 0
        self.cancels: list[str] = []

    @staticmethod
    def _resolve(value: object) -> object:
        if isinstance(value, Exception):
            raise value
        return value

    async def submit_image_to_video(
        self, request: VideoGenerationRequest, *, model: str, image: Path
    ) -> KlingJob:
        self.submits += 1
        return self._resolve(self._submit_result)  # type: ignore[return-value]

    async def get_job(self, task_id: str) -> KlingJob:
        index = min(self.polls, len(self._poll_results) - 1)
        self.polls += 1
        return self._resolve(self._poll_results[index])  # type: ignore[return-value]

    async def cancel_job(self, task_id: str) -> None:
        self.cancels.append(task_id)

    async def download(self, url: str) -> bytes:
        self.downloads += 1
        return self._resolve(self._download_result)  # type: ignore[return-value]


def _settings(**overrides: object) -> VideoProviderSettings:
    defaults: dict[str, object] = {
        "provider": "kling",
        "api_key": "test-key",
        "model": "kling-v1",
        "timeout": 5.0,
        "retry_count": 2,
        "poll_interval": 0.001,
        "poll_timeout": 60.0,
    }
    defaults.update(overrides)
    return VideoProviderSettings.model_validate(defaults)


def _provider(
    tmp_path: Path,
    client: _FakeClient | None = None,
    *,
    settings: VideoProviderSettings | None = None,
    clock: object = None,
    on_progress: object = None,
) -> KlingVideoProvider:
    async def _no_sleep(_seconds: float) -> None:
        return None

    return KlingVideoProvider(
        settings or _settings(),
        tmp_path / "video_clips",
        client=client or _FakeClient(),
        on_progress=on_progress,  # type: ignore[arg-type]
        clock=clock or (lambda: 0.0),  # type: ignore[arg-type]
        sleep=_no_sleep,
    )


def _request(tmp_path: Path, *, with_image: bool = True) -> VideoGenerationRequest:
    images: tuple[Path, ...] = ()
    if with_image:
        image = tmp_path / "001.png"
        image.write_bytes(b"png")
        images = (image,)
    return VideoGenerationRequest(
        scene_id=1, prompt="a cliff", duration=5.0, reference_images=images
    )


# --- contract --------------------------------------------------------------


def test_name_and_supported_models(tmp_path: Path) -> None:
    provider = _provider(tmp_path)

    assert provider.name == "kling"
    assert "kling-v1" in provider.supported_models()


def test_health_check_is_ok_when_configured(tmp_path: Path) -> None:
    health = asyncio.run(_provider(tmp_path).health_check())

    assert health.status is HealthStatus.OK
    assert "kling-v1" in health.detail


def test_health_check_fails_without_an_api_key(tmp_path: Path) -> None:
    provider = KlingVideoProvider(VideoProviderSettings(provider="kling", api_key=None), tmp_path)

    health = asyncio.run(provider.health_check())

    assert health.status is HealthStatus.FAIL
    assert "no API key" in health.detail


def test_health_check_warns_on_an_unknown_model(tmp_path: Path) -> None:
    provider = _provider(tmp_path, settings=_settings(model="kling-v9-imaginary"))

    health = asyncio.run(provider.health_check())

    assert health.status is HealthStatus.WARN
    assert "not a known Kling model" in health.detail


def test_generating_without_an_api_key_gives_a_clean_error(tmp_path: Path) -> None:
    provider = KlingVideoProvider(VideoProviderSettings(provider="kling", api_key=None), tmp_path)

    with pytest.raises(VideoProviderError, match="not configured"):
        asyncio.run(provider.generate(_request(tmp_path)))


def test_the_api_key_is_read_from_a_secret(tmp_path: Path) -> None:
    settings = VideoProviderSettings(provider="kling", api_key=SecretStr("shhh"), model="kling-v1")

    provider = KlingVideoProvider(settings, tmp_path)

    assert asyncio.run(provider.health_check()).status is HealthStatus.OK


# --- job lifecycle ---------------------------------------------------------


def test_submit_job_returns_the_task(tmp_path: Path) -> None:
    client = _FakeClient()

    job = asyncio.run(_provider(tmp_path, client).submit_job(_request(tmp_path)))

    assert job.task_id == "task-1"
    assert client.submits == 1


def test_submit_job_requires_a_reference_image(tmp_path: Path) -> None:
    with pytest.raises(VideoProviderError, match="needs a reference image"):
        asyncio.run(_provider(tmp_path).submit_job(_request(tmp_path, with_image=False)))


def test_poll_job_waits_until_the_task_completes(tmp_path: Path) -> None:
    client = _FakeClient(
        poll_results=[
            KlingJob(task_id="task-1", status=VideoJobStatus.QUEUED),
            KlingJob(task_id="task-1", status=VideoJobStatus.RUNNING),
            KlingJob(
                task_id="task-1", status=VideoJobStatus.COMPLETED, video_url="u", duration=5.0
            ),
        ]
    )

    job = asyncio.run(_provider(tmp_path, client).poll_job("task-1"))

    assert job.status is VideoJobStatus.COMPLETED
    assert client.polls == 3


def test_poll_job_raises_on_a_failed_task(tmp_path: Path) -> None:
    client = _FakeClient(
        poll_results=[
            KlingJob(task_id="task-1", status=VideoJobStatus.FAILED, message="nsfw content")
        ]
    )

    with pytest.raises(VideoProviderError, match="nsfw content"):
        asyncio.run(_provider(tmp_path, client).poll_job("task-1"))


def test_poll_job_times_out_and_cancels_the_job(tmp_path: Path) -> None:
    client = _FakeClient(poll_results=[KlingJob(task_id="task-1", status=VideoJobStatus.RUNNING)])
    ticks = iter([0.0, 0.0, 999.0, 999.0, 999.0])
    provider = _provider(
        tmp_path, client, settings=_settings(poll_timeout=10.0), clock=lambda: next(ticks)
    )

    with pytest.raises(VideoProviderError, match="did not finish within"):
        asyncio.run(provider.poll_job("task-1"))

    assert client.cancels == ["task-1"]  # no orphaned job left billing


def test_download_result_writes_the_clip(tmp_path: Path) -> None:
    client = _FakeClient(download_result=b"mp4-bytes")
    job = KlingJob(task_id="task-1", status=VideoJobStatus.COMPLETED, video_url="u", duration=5.0)

    path = asyncio.run(_provider(tmp_path, client).download_result(job, clip_id=2))

    assert path == tmp_path / "video_clips" / "shot_002.mp4"
    assert path.read_bytes() == b"mp4-bytes"


def test_download_result_without_a_url_raises(tmp_path: Path) -> None:
    job = KlingJob(task_id="task-1", status=VideoJobStatus.COMPLETED, video_url=None)

    with pytest.raises(VideoProviderError, match="without a video URL"):
        asyncio.run(_provider(tmp_path).download_result(job, clip_id=1))


def test_cancel_job_reaches_the_client(tmp_path: Path) -> None:
    client = _FakeClient()

    asyncio.run(_provider(tmp_path, client).cancel_job("task-9"))

    assert client.cancels == ["task-9"]


# --- generate (submit → poll → download) -----------------------------------


def test_generate_runs_the_whole_lifecycle(tmp_path: Path) -> None:
    client = _FakeClient()

    result = asyncio.run(_provider(tmp_path, client).generate(_request(tmp_path)))

    assert (client.submits, client.polls, client.downloads) == (1, 1, 1)
    assert result.status is VideoJobStatus.COMPLETED
    assert result.provider == "kling"
    assert result.model == "kling-v1"
    assert result.remote_job_id == "task-1"
    assert result.video_path == tmp_path / "video_clips" / "shot_001.mp4"
    assert result.duration == 5.0


def test_generate_reports_every_phase(tmp_path: Path) -> None:
    phases: list[str] = []

    asyncio.run(
        _provider(tmp_path, on_progress=lambda _s, phase: phases.append(phase)).generate(
            _request(tmp_path)
        )
    )

    assert phases == ["submitting", "waiting", "downloading", "completed"]


def test_generate_estimates_cost_from_the_configured_rate(tmp_path: Path) -> None:
    provider = _provider(tmp_path, settings=_settings(cost_per_second=0.28))

    result = asyncio.run(provider.generate(_request(tmp_path)))

    assert result.metadata["cost"] == pytest.approx(1.4)


def test_cost_is_zero_when_no_rate_is_configured(tmp_path: Path) -> None:
    result = asyncio.run(_provider(tmp_path).generate(_request(tmp_path)))

    assert result.metadata["cost"] == 0.0


# --- retry -----------------------------------------------------------------


def test_a_transient_failure_is_retried_then_succeeds(tmp_path: Path) -> None:
    client = _FakeClient(
        poll_results=[
            ProviderUnavailableError("503"),
            KlingJob(
                task_id="task-1", status=VideoJobStatus.COMPLETED, video_url="u", duration=5.0
            ),
        ]
    )

    job = asyncio.run(_provider(tmp_path, client).poll_job("task-1"))

    assert job.status is VideoJobStatus.COMPLETED
    assert client.polls == 2


def test_a_rate_limit_is_retried(tmp_path: Path) -> None:
    client = _FakeClient(
        poll_results=[
            RateLimitError("429"),
            KlingJob(
                task_id="task-1", status=VideoJobStatus.COMPLETED, video_url="u", duration=5.0
            ),
        ]
    )

    asyncio.run(_provider(tmp_path, client).poll_job("task-1"))

    assert client.polls == 2


def test_retries_are_exhausted_and_translated(tmp_path: Path) -> None:
    client = _FakeClient(submit_result=ProviderUnavailableError("503 always"))
    provider = _provider(tmp_path, client, settings=_settings(retry_count=2))

    with pytest.raises(VideoProviderError, match="Kling submit failed"):
        asyncio.run(provider.submit_job(_request(tmp_path)))

    assert client.submits == 3  # initial attempt + 2 retries


def test_a_terminal_error_is_not_retried(tmp_path: Path) -> None:
    client = _FakeClient(submit_result=AuthenticationError("bad key"))

    with pytest.raises(VideoProviderError, match="bad key"):
        asyncio.run(_provider(tmp_path, client).submit_job(_request(tmp_path)))

    assert client.submits == 1


def test_a_provider_outage_never_crashes_the_caller(tmp_path: Path) -> None:
    """Every failure arrives as an AppError descendant, not a raw exception."""
    client = _FakeClient(submit_result=ProviderUnavailableError("down"))
    provider = _provider(tmp_path, client, settings=_settings(retry_count=0))

    with pytest.raises(VideoProviderError) as excinfo:
        asyncio.run(provider.generate(_request(tmp_path)))

    assert excinfo.value.context["scene"] == 1
