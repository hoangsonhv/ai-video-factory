"""Persist a built ``Movie`` to ``output/movie.json`` (UTF-8)."""

from __future__ import annotations

import json
from pathlib import Path

from ai_video_factory.domain.value_objects.movie import Movie


def write_movie_json(path: Path, movie: Movie) -> None:
    """Write ``movie`` to ``path`` as UTF-8 JSON (Vietnamese-safe)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(movie.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
