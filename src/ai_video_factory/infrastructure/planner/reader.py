"""Read the shot planner's inputs and persist its outputs (UTF-8)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from ai_video_factory.domain.value_objects.continuity import CharacterBible, WorldBible
from ai_video_factory.domain.value_objects.director import DirectedMovie
from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.domain.value_objects.shot_plan import ShotPlan, ShotStatistics
from ai_video_factory.domain.value_objects.storyboard import Storyboard
from ai_video_factory.infrastructure.planner.errors import PlannerError


def _load[M: BaseModel](path: Path, model: type[M], label: str) -> M:
    if not path.is_file():
        raise PlannerError(f"{label} not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PlannerError(f"invalid JSON in {path}", context={"error": str(exc)}) from exc
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise PlannerError(
            f"{path} does not match the {label} schema", context={"error": str(exc)}
        ) from exc


def read_storyboard(path: Path) -> Storyboard:
    """Load the storyboard the plan is built from."""
    return _load(path, Storyboard, "storyboard")


def read_character_bible(path: Path) -> CharacterBible:
    """Load the character bible the prompts are anchored to."""
    return _load(path, CharacterBible, "character bible")


def read_world_bible(path: Path) -> WorldBible:
    """Load the world bible supplying locations, palette and art direction."""
    return _load(path, WorldBible, "world bible")


def read_directed_movie(path: Path) -> DirectedMovie | None:
    """Load the directed movie, which supplies dialogue and locations.

    Returns ``None`` when the file is absent: a plan can still be built from
    the storyboard alone, it simply cannot recognise a conversation scene. That
    is a smaller loss than refusing to run.
    """
    if not path.is_file():
        return None
    return _load(path, DirectedMovie, "directed movie")


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_plan(path: Path, plan: ShotPlan) -> None:
    """Write the shot plan as UTF-8 JSON."""
    _write(path, plan.model_dump())


def write_statistics(path: Path, statistics: ShotStatistics) -> None:
    """Write the histograms as UTF-8 JSON."""
    _write(path, statistics.model_dump())


def write_prompts(path: Path, prompts: tuple[ImagePrompt, ...]) -> None:
    """Write the prompts, keeping the existing image-prompt shape."""
    _write(path, {"image_prompts": [prompt.model_dump() for prompt in prompts]})
