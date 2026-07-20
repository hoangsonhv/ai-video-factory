"""Persist final-video metadata to a JSON file."""

from __future__ import annotations

import json
from pathlib import Path

from ai_video_factory.infrastructure.asset_pipeline.models import AssetResult


def write_video_metadata(path: Path, result: AssetResult) -> None:
    """Write the video metadata (duration/fps/resolution/counts) as UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "duration": result.duration,
        "fps": result.metadata.get("fps"),
        "resolution": result.metadata.get("resolution"),
        "image_count": result.metadata.get("image_count"),
        "subtitle_count": result.metadata.get("subtitle_count"),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
