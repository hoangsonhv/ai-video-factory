"""Persist generated story artifacts (ideas, outline) to JSON files."""

from __future__ import annotations

import json
from pathlib import Path

from ai_video_factory.domain.value_objects.chapter import StoryChapter
from ai_video_factory.domain.value_objects.idea import IdeaBrief, StoryIdea
from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.domain.value_objects.outline import StoryOutline


def write_ideas_json(path: Path, brief: IdeaBrief, ideas: list[StoryIdea]) -> None:
    """Write ``ideas`` (and the originating brief) to ``path`` as UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "brief": brief.model_dump(),
        "ideas": [idea.model_dump() for idea in ideas],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_outline_json(path: Path, outline: StoryOutline) -> None:
    """Write ``outline`` to ``path`` as UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(outline.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def write_chapter_json(path: Path, chapter: StoryChapter) -> None:
    """Write ``chapter`` to ``path`` as UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(chapter.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def write_image_prompts_json(path: Path, prompts: list[ImagePrompt]) -> None:
    """Write ``prompts`` to ``path`` as UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"image_prompts": [prompt.model_dump() for prompt in prompts]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
