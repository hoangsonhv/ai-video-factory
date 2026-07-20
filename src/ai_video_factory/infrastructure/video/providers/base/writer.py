"""Persist a video-clip generation manifest to JSON."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ai_video_factory.infrastructure.video.providers.base.models import VideoGenerationResult

MANIFEST_FILENAME = "manifest.json"


class VideoManifestEntry(BaseModel):
    """One clip described in ``output/video_clips/manifest.json``.

    ``estimated_cost`` is what the run projected before submitting;
    ``actual_cost`` is what the finished job worked out to. They differ when a
    provider returns a duration other than the one requested, and
    ``actual_cost`` is ``0.0`` for a scene that failed (nothing was rendered).
    Both are ``0.0`` when no ``cost_per_second`` rate is configured — meaning
    *unknown*, not *free*.
    """

    model_config = ConfigDict(frozen=True)

    scene_id: int
    clip_id: int = 1
    shot_ids: tuple[int, ...] = ()
    provider: str
    model: str
    status: str
    duration: float
    estimated_cost: float
    actual_cost: float
    remote_job_id: str | None
    filename: str | None


def _actual_cost(result: VideoGenerationResult) -> float:
    """The cost the provider reported, or ``0.0`` when it reported none."""
    raw = result.metadata.get("cost")
    if isinstance(raw, int | float):
        return float(raw)
    return 0.0


def to_manifest_entry(
    result: VideoGenerationResult, *, estimated_cost: float = 0.0
) -> VideoManifestEntry:
    """Describe one generation result for the manifest."""
    return VideoManifestEntry(
        scene_id=result.scene_id,
        clip_id=result.clip_id,
        shot_ids=result.shot_ids,
        provider=result.provider,
        model=result.model,
        status=result.status.value,
        duration=result.duration,
        estimated_cost=round(estimated_cost, 4),
        actual_cost=_actual_cost(result),
        remote_job_id=result.remote_job_id,
        filename=result.video_path.name if result.video_path else None,
    )


def write_video_manifest(
    path: Path,
    results: Sequence[VideoGenerationResult],
    *,
    estimates: Mapping[int, float] | None = None,
) -> None:
    """Write the clip manifest as UTF-8 JSON.

    ``estimates`` maps a scene id to the cost projected for it before the run
    (see :class:`GenerationPlan`); scenes absent from it record ``0.0``.
    """
    per_scene = estimates or {}
    entries = [
        to_manifest_entry(result, estimated_cost=per_scene.get(result.scene_id, 0.0))
        for result in results
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "count": len(entries),
        "total_estimated_cost": round(sum(entry.estimated_cost for entry in entries), 4),
        "total_actual_cost": round(sum(entry.actual_cost for entry in entries), 4),
        "clips": [entry.model_dump() for entry in entries],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
