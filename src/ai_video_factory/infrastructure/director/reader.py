"""Read the movie to direct, and persist the directed movie (UTF-8)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from ai_video_factory.domain.value_objects.character_library import CharacterLibrary
from ai_video_factory.domain.value_objects.director import DirectedMovie
from ai_video_factory.domain.value_objects.movie import Movie
from ai_video_factory.infrastructure.director.errors import DirectorError


def read_movie(path: Path) -> Movie:
    """Load a :class:`Movie` from a saved movie JSON file.

    Accepts ``movie.json`` or ``movie_consistent.json`` — both are movies.

    Raises:
        DirectorError: If the file is missing, malformed, or invalid.
    """
    if not path.is_file():
        raise DirectorError(f"movie file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DirectorError(f"invalid JSON in {path}", context={"error": str(exc)}) from exc
    try:
        return Movie.model_validate(data)
    except ValidationError as exc:
        raise DirectorError("movie does not match schema", context={"error": str(exc)}) from exc


def read_optional_library(path: Path) -> CharacterLibrary | None:
    """Load the character library if it exists, else ``None``.

    The library supplies each character's master prompt so the directed prompt
    keeps identities fixed. Directing without it still works — the prompt then
    carries camera and motion language only.

    Raises:
        DirectorError: If the file exists but is malformed or invalid.
    """
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DirectorError(f"invalid JSON in {path}", context={"error": str(exc)}) from exc
    try:
        return CharacterLibrary.model_validate(data)
    except ValidationError as exc:
        raise DirectorError(
            "character library does not match schema", context={"error": str(exc)}
        ) from exc


def read_optional_directed_movie(*paths: Path) -> DirectedMovie | None:
    """Load the first directed movie that exists, for ``--resume``.

    Paths are tried in order (typically the partial output before the complete
    one), so a resumed run picks up the most recent progress.

    Raises:
        DirectorError: If a file exists but is malformed or invalid.
    """
    for path in paths:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DirectorError(f"invalid JSON in {path}", context={"error": str(exc)}) from exc
        try:
            return DirectedMovie.model_validate(data)
        except ValidationError as exc:
            raise DirectorError(
                f"{path} does not match the directed-movie schema",
                context={"error": str(exc)},
            ) from exc
    return None


def write_directed_movie_json(path: Path, movie: DirectedMovie) -> None:
    """Write ``movie`` to ``path`` as UTF-8 JSON (Vietnamese-safe)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(movie.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
