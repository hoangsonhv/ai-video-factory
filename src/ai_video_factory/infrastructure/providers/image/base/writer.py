"""Persist an image-generation manifest to a JSON file."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class ImageManifestEntry(BaseModel):
    """One image described in ``output/images/manifest.json``."""

    model_config = ConfigDict(frozen=True)

    index: int
    filename: str
    prompt: str
    provider: str
    model: str
    width: int
    height: int
    created_at: str


def write_images_manifest(path: Path, entries: Sequence[ImageManifestEntry]) -> None:
    """Write the image manifest as UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "count": len(entries),
        "images": [entry.model_dump() for entry in entries],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
