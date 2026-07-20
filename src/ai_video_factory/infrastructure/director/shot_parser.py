"""Parse the director's one-shot batch answer into shots (pure, no I/O).

The model returns a single ``{"scenes": [{"scene_id": n, "shots": [...]}, ...]}``
document covering every scene. This module turns that into
``{scene_id: [Shot, ...]}``, repairing what can be repaired deterministically:

- shot ids are **renumbered** 1..N per scene, so ordering is ours, not the
  model's;
- durations are **clamped** into the permitted 2-5 second range, and a missing
  or unusable duration falls back to an even split of the scene's length;
- more shots than the maximum are **trimmed**.

Anything structural that cannot be repaired — no JSON, no scenes, a scene with
no usable shots — is reported rather than guessed at.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from ai_video_factory.domain.value_objects.director import Shot
from ai_video_factory.infrastructure.director.errors import DirectorError
from ai_video_factory.infrastructure.director.shot_planner import (
    MAX_SHOTS,
    clamp_shot_duration,
    split_evenly,
)
from ai_video_factory.infrastructure.story.json_extract import loads_json

_SHOT_TEXT_FIELDS = (
    "camera",
    "camera_motion",
    "lens",
    "framing",
    "subject",
    "action",
    "expression",
    "environment_motion",
    "lighting",
    "transition",
    "video_prompt",
)


def _scene_id(block: Mapping[str, Any]) -> int | None:
    raw = block.get("scene_id", block.get("id"))
    if not isinstance(raw, str | int | float):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _duration(raw: object) -> int | None:
    if not isinstance(raw, str | int | float):
        return None
    try:
        value = int(float(raw))
    except (TypeError, ValueError):
        return None
    return clamp_shot_duration(value) if value > 0 else None


def _text(raw: object) -> str:
    if isinstance(raw, str):
        return " ".join(raw.split()).strip()
    if isinstance(raw, int | float):
        return str(raw)
    return ""


def _shot_blocks(block: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = block.get("shots")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def parse_scene_shots(block: Mapping[str, Any], scene_duration: int) -> list[Shot]:
    """Turn one scene block into an ordered, renumbered, clamped shot list.

    Returns an empty list when the block carries no usable shot.
    """
    blocks = _shot_blocks(block)[:MAX_SHOTS]
    if not blocks:
        return []

    fallback = split_evenly(scene_duration, len(blocks))
    shots: list[Shot] = []
    for index, raw in enumerate(blocks):
        duration = _duration(raw.get("duration")) or fallback[index]
        fields = {name: _text(raw.get(name)) for name in _SHOT_TEXT_FIELDS}
        try:
            shots.append(Shot(id=index + 1, duration=duration, **fields))
        except ValidationError as exc:  # pragma: no cover - clamping precedes this
            raise DirectorError("shot does not match schema", context={"error": str(exc)}) from exc
    return shots


def parse_shot_plan(content: str, durations: Mapping[int, int]) -> dict[int, list[Shot]]:
    """Parse the batch answer into ``{scene_id: shots}``.

    ``durations`` maps each scene id to its length, used when the model gives a
    shot no usable duration of its own.

    Raises:
        DirectorError: If the content is not valid JSON, carries no scenes, or
            yields no usable shots at all.
    """
    try:
        data = loads_json(content, strict=False)
    except json.JSONDecodeError as exc:
        raise DirectorError("director returned invalid JSON", context={"error": str(exc)}) from exc

    raw = data.get("scenes") if isinstance(data, dict) else data
    if not isinstance(raw, list) or not raw:
        raise DirectorError("director returned no scenes")

    plan: dict[int, list[Shot]] = {}
    for block in raw:
        if not isinstance(block, dict):
            continue
        scene_id = _scene_id(block)
        if scene_id is None:
            continue
        shots = parse_scene_shots(block, durations.get(scene_id, 0))
        if shots:
            plan[scene_id] = shots

    if not plan:
        raise DirectorError("director returned no usable shots")
    return plan
