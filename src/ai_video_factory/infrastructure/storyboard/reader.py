"""Read the directed movie and persist the storyboard (UTF-8)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from ai_video_factory.domain.value_objects.character_library import CharacterLibrary
from ai_video_factory.domain.value_objects.director import DirectedMovie
from ai_video_factory.domain.value_objects.storyboard import Storyboard
from ai_video_factory.infrastructure.storyboard.errors import StoryboardError


def read_directed_movie(path: Path) -> DirectedMovie:
    """Load a :class:`DirectedMovie` from ``movie_directed.json``.

    Raises:
        StoryboardError: If the file is missing, malformed, or invalid.
    """
    if not path.is_file():
        raise StoryboardError(f"directed movie not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StoryboardError(f"invalid JSON in {path}", context={"error": str(exc)}) from exc
    try:
        return DirectedMovie.model_validate(data)
    except ValidationError as exc:
        raise StoryboardError(
            f"{path} does not match the directed-movie schema; re-run `director`",
            context={"error": str(exc)},
        ) from exc


def read_optional_library(path: Path) -> CharacterLibrary | None:
    """Load the character library if present, else ``None``.

    Raises:
        StoryboardError: If the file exists but is malformed or invalid.
    """
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StoryboardError(f"invalid JSON in {path}", context={"error": str(exc)}) from exc
    try:
        return CharacterLibrary.model_validate(data)
    except ValidationError as exc:
        raise StoryboardError(
            "character library does not match schema", context={"error": str(exc)}
        ) from exc


def write_storyboard_json(path: Path, storyboard: Storyboard) -> None:
    """Write ``storyboard`` to ``path`` as UTF-8 JSON (Vietnamese-safe)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(storyboard.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
