"""Kling job models and status mapping (no HTTP, no vendor SDK).

Kling is asynchronous: a submission returns a task id, and the task is polled
until it succeeds or fails. These types normalize the vendor's payload into
something the provider can reason about; the vendor's own status vocabulary is
mapped onto the shared :class:`VideoJobStatus`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ai_video_factory.infrastructure.video.providers.base.models import VideoJobStatus

_STATUS_MAP: dict[str, VideoJobStatus] = {
    "submitted": VideoJobStatus.QUEUED,
    "queued": VideoJobStatus.QUEUED,
    "pending": VideoJobStatus.QUEUED,
    "processing": VideoJobStatus.RUNNING,
    "running": VideoJobStatus.RUNNING,
    "succeed": VideoJobStatus.COMPLETED,
    "succeeded": VideoJobStatus.COMPLETED,
    "success": VideoJobStatus.COMPLETED,
    "completed": VideoJobStatus.COMPLETED,
    "failed": VideoJobStatus.FAILED,
    "failure": VideoJobStatus.FAILED,
    "error": VideoJobStatus.FAILED,
}


def map_task_status(raw: str) -> VideoJobStatus:
    """Map a Kling ``task_status`` onto the shared status enum.

    An unrecognised status is treated as ``RUNNING`` rather than a failure, so
    a vendor-side vocabulary change stalls a poll instead of silently
    discarding a job that is still rendering.
    """
    return _STATUS_MAP.get(raw.strip().lower(), VideoJobStatus.RUNNING)


class KlingJob(BaseModel):
    """One Kling task, normalized."""

    model_config = ConfigDict(frozen=True)

    task_id: str = Field(min_length=1)
    status: VideoJobStatus
    video_url: str | None = None
    duration: float = Field(default=0.0, ge=0.0)
    message: str = ""

    @property
    def is_terminal(self) -> bool:
        """Whether the job has stopped changing (succeeded or failed)."""
        return self.status in (VideoJobStatus.COMPLETED, VideoJobStatus.FAILED)
