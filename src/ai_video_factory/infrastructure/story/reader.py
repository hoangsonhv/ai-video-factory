"""Read a selected story idea from a saved ideas JSON file."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from ai_video_factory.domain.value_objects.chapter import StoryChapter
from ai_video_factory.domain.value_objects.idea import StoryIdea
from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.domain.value_objects.outline import StoryOutline
from ai_video_factory.infrastructure.story.errors import (
    ChapterParseError,
    IdeaParseError,
    ImagePromptParseError,
    OutlineParseError,
)


def read_idea(path: Path, index: int) -> StoryIdea:
    """Load the idea at ``index`` from an ideas JSON file (from the ``idea`` command).

    Accepts either an object with an ``"ideas"`` array or a bare array.

    Raises:
        IdeaParseError: If the file is missing, malformed, the index is out of
            range, or the selected idea fails validation.
    """
    if not path.is_file():
        raise IdeaParseError(f"ideas file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise IdeaParseError(f"invalid JSON in {path}", context={"error": str(exc)}) from exc

    ideas = data.get("ideas") if isinstance(data, dict) else data
    if not isinstance(ideas, list):
        raise IdeaParseError(f"no 'ideas' array in {path}")
    if index < 0 or index >= len(ideas):
        raise IdeaParseError(f"idea index {index} out of range (0..{len(ideas) - 1})")

    try:
        return StoryIdea.model_validate(ideas[index])
    except ValidationError as exc:
        raise IdeaParseError(
            "selected idea does not match schema", context={"error": str(exc)}
        ) from exc


def read_outline(path: Path) -> StoryOutline:
    """Load a :class:`StoryOutline` from a saved outline JSON file.

    Raises:
        OutlineParseError: If the file is missing, malformed, or invalid.
    """
    if not path.is_file():
        raise OutlineParseError(f"outline file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OutlineParseError(f"invalid JSON in {path}", context={"error": str(exc)}) from exc
    try:
        return StoryOutline.model_validate(data)
    except ValidationError as exc:
        raise OutlineParseError(
            "outline does not match schema", context={"error": str(exc)}
        ) from exc


def read_chapter(path: Path) -> StoryChapter:
    """Load a :class:`StoryChapter` from a saved chapter JSON file.

    Raises:
        ChapterParseError: If the file is missing, malformed, or invalid.
    """
    if not path.is_file():
        raise ChapterParseError(f"chapter file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ChapterParseError(f"invalid JSON in {path}", context={"error": str(exc)}) from exc
    try:
        return StoryChapter.model_validate(data)
    except ValidationError as exc:
        raise ChapterParseError(
            "chapter does not match schema", context={"error": str(exc)}
        ) from exc


def read_image_prompts(path: Path) -> list[ImagePrompt]:
    """Load image prompts from a saved image-prompts JSON file.

    Accepts an object with an ``"image_prompts"`` array or a bare array.

    Raises:
        ImagePromptParseError: If the file is missing, malformed, or invalid.
    """
    if not path.is_file():
        raise ImagePromptParseError(f"image prompts file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ImagePromptParseError(f"invalid JSON in {path}", context={"error": str(exc)}) from exc

    raw = data.get("image_prompts") if isinstance(data, dict) else data
    if not isinstance(raw, list) or not raw:
        raise ImagePromptParseError(f"no image prompts in {path}")
    try:
        return [ImagePrompt.model_validate(item) for item in raw]
    except ValidationError as exc:
        raise ImagePromptParseError(
            "image prompt does not match schema", context={"error": str(exc)}
        ) from exc
