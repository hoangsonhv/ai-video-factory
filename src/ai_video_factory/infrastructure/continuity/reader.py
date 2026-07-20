"""Read the continuity inputs and persist its outputs (UTF-8)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from ai_video_factory.domain.value_objects.character_library import CharacterLibrary
from ai_video_factory.domain.value_objects.continuity import (
    CharacterBible,
    PromptScoreDocument,
    VisualContextDocument,
    WorldBible,
)
from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.domain.value_objects.movie import Movie
from ai_video_factory.domain.value_objects.storyboard import Storyboard
from ai_video_factory.infrastructure.continuity.errors import ContinuityError


def _load[M: BaseModel](path: Path, model: type[M], label: str) -> M:
    if not path.is_file():
        raise ContinuityError(f"{label} not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContinuityError(f"invalid JSON in {path}", context={"error": str(exc)}) from exc
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ContinuityError(
            f"{path} does not match the {label} schema", context={"error": str(exc)}
        ) from exc


def read_storyboard(path: Path) -> Storyboard:
    """Load the storyboard the continuity engine works from."""
    return _load(path, Storyboard, "storyboard")


def read_character_library(path: Path) -> CharacterLibrary:
    """Load the character library the character bible is derived from."""
    return _load(path, CharacterLibrary, "character library")


def read_movie(path: Path) -> Movie:
    """Load the movie the world bible is derived from."""
    return _load(path, Movie, "movie")


def read_optional_character_bible(path: Path) -> CharacterBible | None:
    """Load a hand-edited character bible, if one exists."""
    return _load(path, CharacterBible, "character bible") if path.is_file() else None


def read_optional_world_bible(path: Path) -> WorldBible | None:
    """Load a hand-edited world bible, if one exists."""
    return _load(path, WorldBible, "world bible") if path.is_file() else None


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_character_bible(path: Path, bible: CharacterBible) -> None:
    """Write the character bible as UTF-8 JSON."""
    _write(path, bible.model_dump())


def write_world_bible(path: Path, bible: WorldBible) -> None:
    """Write the world bible as UTF-8 JSON."""
    _write(path, bible.model_dump())


def write_visual_context(path: Path, context: VisualContextDocument) -> None:
    """Write the per-shot visual contexts as UTF-8 JSON."""
    _write(path, context.model_dump())


def write_shot_image_prompts(path: Path, prompts: tuple[ImagePrompt, ...]) -> None:
    """Write the continuity prompts in the existing image-prompt shape.

    Kept schema-compatible with ``image_prompts.json`` so the image stage can
    be pointed here by a later sprint without a migration.
    """
    _write(path, {"image_prompts": [prompt.model_dump() for prompt in prompts]})


def write_prompt_scores(path: Path, scores: PromptScoreDocument) -> None:
    """Write the per-prompt continuity scores as UTF-8 JSON."""
    payload = scores.model_dump()
    payload["average"] = scores.average
    payload["failing"] = [score.shot_id for score in scores.failing]
    _write(path, payload)
