"""Estimate what a video-generation run will submit and spend.

The single source of truth for both the ``--dry-run`` preview and the
manifest's ``estimated_cost``, so the number a user is shown before confirming
is the same number recorded afterwards.

Estimates are derived from the configured ``cost_per_second`` rate. Providers
do not return a price, so a rate of ``0.0`` means *unknown* — never *free*.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from ai_video_factory.infrastructure.config.settings import VideoProviderSettings
from ai_video_factory.infrastructure.video.providers.base.models import VideoGenerationRequest

MOCK_PROVIDER_NAME = "mock"


def estimate_cost(duration: float, settings: VideoProviderSettings) -> float:
    """Cost of ``duration`` seconds at the configured rate."""
    return round(max(duration, 0.0) * settings.cost_per_second, 4)


class GenerationPlan(BaseModel):
    """What a run is about to do, before anything is submitted."""

    model_config = ConfigDict(frozen=True)

    provider: str
    model: str
    scene_count: int = Field(ge=0)
    jobs: int = Field(ge=0)
    total_duration: float = Field(default=0.0, ge=0.0)
    estimated_cost: float = Field(default=0.0, ge=0.0)
    per_scene: dict[int, float] = Field(default_factory=dict)
    limited: bool = False

    @property
    def is_paid(self) -> bool:
        """Whether this run spends money (any provider but the local mock)."""
        return self.provider != MOCK_PROVIDER_NAME

    @property
    def cost_is_known(self) -> bool:
        """Whether a rate was configured; otherwise the cost is unknown."""
        return self.estimated_cost > 0.0

    def scene_estimate(self, scene_id: int) -> float:
        """The estimated cost recorded for ``scene_id`` (``0.0`` if absent)."""
        return self.per_scene.get(scene_id, 0.0)


def build_plan(
    requests: Sequence[VideoGenerationRequest],
    settings: VideoProviderSettings,
    *,
    scene_count: int | None = None,
) -> GenerationPlan:
    """Summarize what ``requests`` will submit and cost.

    ``scene_count`` is the movie's full scene count; when it exceeds the number
    of requests the plan is marked ``limited`` (``--limit`` was applied).
    """
    per_scene = {
        request.scene_id: estimate_cost(request.duration, settings) for request in requests
    }
    total_duration = sum(request.duration for request in requests)
    total = scene_count if scene_count is not None else len(requests)
    return GenerationPlan(
        provider=settings.provider,
        model=settings.model,
        scene_count=total,
        jobs=len(requests),
        total_duration=round(total_duration, 3),
        estimated_cost=round(sum(per_scene.values()), 4),
        per_scene=per_scene,
        limited=len(requests) < total,
    )
