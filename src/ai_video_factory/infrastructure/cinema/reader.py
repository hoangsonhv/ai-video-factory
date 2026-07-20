"""Read the cinematic director's inputs and persist its outputs (UTF-8)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from ai_video_factory.domain.value_objects.cinema import CinematicDirection
from ai_video_factory.domain.value_objects.continuity import CharacterBible, WorldBible
from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.domain.value_objects.storyboard import Storyboard
from ai_video_factory.infrastructure.cinema.errors import CinemaError


def _load[M: BaseModel](path: Path, model: type[M], label: str) -> M:
    if not path.is_file():
        raise CinemaError(f"{label} not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CinemaError(f"invalid JSON in {path}", context={"error": str(exc)}) from exc
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise CinemaError(
            f"{path} does not match the {label} schema", context={"error": str(exc)}
        ) from exc


def read_storyboard(path: Path) -> Storyboard:
    """Load the storyboard the director works from."""
    return _load(path, Storyboard, "storyboard")


def read_character_bible(path: Path) -> CharacterBible:
    """Load the character bible the prompts are anchored to."""
    return _load(path, CharacterBible, "character bible")


def read_world_bible(path: Path) -> WorldBible:
    """Load the world bible supplying palette and art direction."""
    return _load(path, WorldBible, "world bible")


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_direction(path: Path, direction: CinematicDirection) -> None:
    """Write the scene and shot decisions as UTF-8 JSON."""
    _write(path, direction.model_dump())


def write_prompts(path: Path, prompts: tuple[ImagePrompt, ...]) -> None:
    """Write the prompts, keeping the existing image-prompt shape."""
    _write(path, {"image_prompts": [prompt.model_dump() for prompt in prompts]})
