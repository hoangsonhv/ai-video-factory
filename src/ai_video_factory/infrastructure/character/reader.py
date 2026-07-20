"""Read the movie bible and the character library from disk."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from ai_video_factory.domain.value_objects.character_library import CharacterLibrary
from ai_video_factory.domain.value_objects.movie import Movie
from ai_video_factory.infrastructure.character.errors import CharacterLibraryError


def _load(path: Path, label: str) -> object:
    if not path.is_file():
        raise CharacterLibraryError(f"{label} file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CharacterLibraryError(f"invalid JSON in {path}", context={"error": str(exc)}) from exc


def read_movie(path: Path) -> Movie:
    """Load a :class:`Movie` from a saved ``movie.json``.

    Raises:
        CharacterLibraryError: If the file is missing, malformed, or invalid.
    """
    try:
        return Movie.model_validate(_load(path, "movie"))
    except ValidationError as exc:
        raise CharacterLibraryError(
            "movie does not match schema", context={"error": str(exc)}
        ) from exc


def read_character_library(path: Path) -> CharacterLibrary:
    """Load a :class:`CharacterLibrary` from a saved ``character_library.json``.

    Raises:
        CharacterLibraryError: If the file is missing, malformed, or invalid.
    """
    try:
        return CharacterLibrary.model_validate(_load(path, "character library"))
    except ValidationError as exc:
        raise CharacterLibraryError(
            "character library does not match schema", context={"error": str(exc)}
        ) from exc
