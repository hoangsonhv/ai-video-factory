"""Persist an image-generation manifest to a JSON file."""

from __future__ import annotations

import json
from pathlib import Path

from ai_video_factory.infrastructure.providers.image.base.models import ImageGenerationResponse


def write_images_manifest(path: Path, responses: list[ImageGenerationResponse]) -> None:
    """Write a manifest of the generated images as UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "count": len(responses),
        "images": [
            {
                "index": index,
                "path": str(response.image_path),
                "provider": response.provider,
                "model": response.model,
                "generation_time": response.generation_time,
            }
            for index, response in enumerate(responses, start=1)
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
