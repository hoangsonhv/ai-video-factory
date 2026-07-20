"""Vendor-neutral request/result models for the video provider layer.

These are the contract between the application side (which turns a scene into
a request) and any concrete video provider (which fulfils it). No vendor field
appears here — a future commercial driver maps these onto its own API rather
than the reverse.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ai_video_factory.domain.value_objects.movie import Camera
from ai_video_factory.infrastructure.providers.base.models import ProviderHealth


class VideoJobStatus(StrEnum):
    """Lifecycle of one video-generation job.

    Local providers complete (or fail) synchronously; ``QUEUED`` and
    ``RUNNING`` exist for remote providers that return a job id immediately
    and render asynchronously.
    """

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ClipReferences(BaseModel):
    """The images a provider may condition a clip on, when it supports them.

    Consistency across clips is the whole point: ``character`` pins who is on
    screen, ``scene`` pins where, and ``previous_clip`` lets a provider that
    supports continuation carry the look forward from the shot before. A
    provider that supports none of these simply ignores them — the contract
    offers references, it does not require their use.
    """

    model_config = ConfigDict(frozen=True)

    character: tuple[Path, ...] = ()
    scene: Path | None = None
    previous_clip: Path | None = None

    @property
    def primary(self) -> Path | None:
        """The single best still to condition on: the scene, else a character."""
        if self.scene is not None:
            return self.scene
        return self.character[0] if self.character else None

    @property
    def is_empty(self) -> bool:
        """Whether no reference of any kind is available."""
        return not self.character and self.scene is None and self.previous_clip is None


class VideoGenerationRequest(BaseModel):
    """A request to generate one clip, independent of provider.

    A clip covers one or more consecutive storyboard shots from a single scene
    (``shot_ids``), so it can satisfy a provider's minimum clip length without
    cutting across a scene boundary.
    """

    model_config = ConfigDict(frozen=True)

    scene_id: int = Field(ge=1)
    clip_id: int = Field(default=1, ge=1)
    shot_ids: tuple[int, ...] = ()
    prompt: str = ""
    negative_prompt: str = ""
    duration: float = Field(default=5.0, gt=0.0)
    aspect_ratio: str = "9:16"
    width: int = Field(default=1080, gt=0)
    height: int = Field(default=1920, gt=0)
    fps: int = Field(default=30, gt=0)
    seed: int | None = None
    reference_images: tuple[Path, ...] = ()
    camera: Camera = Field(default_factory=Camera)
    style: str = ""
    motion_level: float = Field(default=0.5, ge=0.0, le=1.0)


class VideoGenerationResult(BaseModel):
    """The outcome of one video-generation job, normalized across providers."""

    model_config = ConfigDict(frozen=True)

    scene_id: int = Field(ge=1)
    clip_id: int = Field(default=1, ge=1)
    shot_ids: tuple[int, ...] = ()
    provider: str
    model: str
    status: VideoJobStatus
    remote_job_id: str | None = None
    video_path: Path | None = None
    preview_path: Path | None = None
    duration: float = Field(default=0.0, ge=0.0)
    metadata: Mapping[str, object] = Field(default_factory=dict)

    @property
    def is_completed(self) -> bool:
        """Whether the job finished successfully."""
        return self.status is VideoJobStatus.COMPLETED


class VideoProviderStatus(BaseModel):
    """One registered provider's identity and health, for reporting."""

    model_config = ConfigDict(frozen=True)

    name: str
    is_default: bool = False
    models: tuple[str, ...] = ()
    health: ProviderHealth
