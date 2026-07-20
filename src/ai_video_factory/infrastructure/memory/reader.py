"""Read the memory stage's inputs and persist its outputs (UTF-8)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, ValidationError

from ai_video_factory.domain.value_objects.character_memory import (
    AppearanceScoreDocument,
    CharacterMemoryDocument,
)
from ai_video_factory.domain.value_objects.continuity import CharacterBible
from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.domain.value_objects.movie import Movie
from ai_video_factory.domain.value_objects.storyboard import Storyboard
from ai_video_factory.infrastructure.memory.errors import CharacterMemoryError

_IMAGE_NUMBER = re.compile(r"(\d+)")


def _load[M: BaseModel](path: Path, model: type[M], label: str) -> M:
    if not path.is_file():
        raise CharacterMemoryError(f"{label} not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CharacterMemoryError(f"invalid JSON in {path}", context={"error": str(exc)}) from exc
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise CharacterMemoryError(
            f"{path} does not match the {label} schema", context={"error": str(exc)}
        ) from exc


def read_storyboard(path: Path) -> Storyboard:
    """Load the storyboard whose shots the prompts belong to."""
    return _load(path, Storyboard, "storyboard")


def read_character_bible(path: Path) -> CharacterBible:
    """Load the character bible a first-run memory is derived from."""
    return _load(path, CharacterBible, "character bible")


def read_movie(path: Path) -> Movie:
    """Load the movie supplying gender and age."""
    return _load(path, Movie, "movie")


def read_optional_memory(path: Path) -> CharacterMemoryDocument | None:
    """Load an existing memory, if the film has one."""
    return _load(path, CharacterMemoryDocument, "character memory") if path.is_file() else None


def read_prompts(path: Path) -> tuple[ImagePrompt, ...]:
    """Load the continuity prompts the memory engine enriches.

    Raises:
        CharacterMemoryError: If the file is missing, malformed, or invalid.
    """
    if not path.is_file():
        raise CharacterMemoryError(
            f"prompts not found: {path}; run `continuity` before the memory engine"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CharacterMemoryError(f"invalid JSON in {path}", context={"error": str(exc)}) from exc
    raw = data.get("image_prompts") if isinstance(data, dict) else data
    if not isinstance(raw, list) or not raw:
        raise CharacterMemoryError(f"no prompts in {path}")
    try:
        return tuple(ImagePrompt.model_validate(item) for item in raw)
    except ValidationError as exc:
        raise CharacterMemoryError(
            "prompt does not match schema", context={"error": str(exc)}
        ) from exc


def scan_images(images_dir: Path) -> dict[int, Path]:
    """Map each generated image to the shot number in its filename.

    ``001.png`` belongs to shot 1. Files that carry no number are ignored
    rather than guessed at.
    """
    if not images_dir.is_dir():
        return {}
    found: dict[int, Path] = {}
    for image in sorted(images_dir.glob("*.png")):
        match = _IMAGE_NUMBER.search(image.stem)
        if match:
            found.setdefault(int(match.group(1)), image)
    return found


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_memory(path: Path, memory: CharacterMemoryDocument) -> None:
    """Write the character memory as UTF-8 JSON."""
    _write(path, memory.model_dump())


def write_prompts(path: Path, prompts: tuple[ImagePrompt, ...]) -> None:
    """Write the enriched prompts, keeping the existing image-prompt shape."""
    _write(path, {"image_prompts": [prompt.model_dump() for prompt in prompts]})


def write_appearance_scores(path: Path, scores: AppearanceScoreDocument) -> None:
    """Write the per-prompt appearance scores as UTF-8 JSON."""
    payload = scores.model_dump()
    payload["average"] = scores.average
    payload["failing"] = [score.shot_id for score in scores.failing]
    _write(path, payload)
