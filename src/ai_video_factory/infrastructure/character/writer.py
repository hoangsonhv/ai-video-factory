"""Persist the character library and the consistency-corrected movie (UTF-8)."""

from __future__ import annotations

import json
from pathlib import Path

from ai_video_factory.domain.value_objects.character_library import CharacterLibrary
from ai_video_factory.domain.value_objects.movie import Movie


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_character_library_json(path: Path, library: CharacterLibrary) -> None:
    """Write ``library`` to ``path`` as UTF-8 JSON (Vietnamese-safe)."""
    _write(path, library.model_dump())


def write_consistent_movie_json(path: Path, movie: Movie) -> None:
    """Write the injected ``movie`` to ``path`` as UTF-8 JSON."""
    _write(path, movie.model_dump())
