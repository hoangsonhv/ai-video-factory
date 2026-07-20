"""Parse the AI provider's JSON output into a validated ``Movie`` model.

Characters are deduplicated by ``id`` keeping the *first* occurrence, which
guarantees a character's appearance is fixed once generated (it can never be
changed by a later mention). Project-level ``style``/``genre``/``duration`` are
injected when the model omits them.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from ai_video_factory.domain.value_objects.movie import Movie
from ai_video_factory.infrastructure.story.errors import MovieBuildError
from ai_video_factory.infrastructure.story.json_extract import loads_json


def _dedupe_characters(characters: object) -> list[Any]:
    """Keep the first character per ``id`` (or ``name``) — appearance is fixed."""
    if not isinstance(characters, list):
        return []
    seen: set[str] = set()
    unique: list[Any] = []
    for character in characters:
        if not isinstance(character, dict):
            continue
        key = str(character.get("id") or character.get("name") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(character)
    return unique


def parse_movie(content: str, *, style: str, genre: str, duration: int) -> Movie:
    """Parse ``content`` (JSON) into a validated :class:`Movie`.

    Raises:
        MovieBuildError: If the content is not valid JSON, is not a JSON object,
            or fails schema validation.
    """
    try:
        data = loads_json(content, strict=False)
    except json.JSONDecodeError as exc:
        raise MovieBuildError(
            "provider returned invalid JSON", context={"error": str(exc)}
        ) from exc

    if not isinstance(data, dict):
        raise MovieBuildError("expected a JSON object describing the movie")

    payload: dict[str, Any] = dict(data)
    payload.setdefault("style", style)
    payload.setdefault("genre", genre)
    if not payload.get("duration"):
        payload["duration"] = duration
    payload["characters"] = _dedupe_characters(payload.get("characters"))

    try:
        return Movie.model_validate(payload)
    except ValidationError as exc:
        raise MovieBuildError("movie does not match schema", context={"error": str(exc)}) from exc
