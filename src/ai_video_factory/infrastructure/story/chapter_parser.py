"""Parse the AI provider's JSON output into a validated ``StoryChapter``.

The model returns only ``title`` and ``content``; the narration duration is
computed deterministically from the content so it does not depend on the LLM.
"""

from __future__ import annotations

import json
import math

from pydantic import ValidationError

from ai_video_factory.domain.value_objects.chapter import StoryChapter
from ai_video_factory.infrastructure.story.errors import ChapterParseError
from ai_video_factory.infrastructure.story.json_extract import loads_json

DEFAULT_WORDS_PER_MINUTE = 150


def estimate_duration_seconds(
    text: str, *, words_per_minute: int = DEFAULT_WORDS_PER_MINUTE
) -> int:
    """Estimate narration seconds for ``text`` at ``words_per_minute``."""
    words = len(text.split())
    if words == 0:
        return 0
    return max(1, math.ceil(words * 60 / words_per_minute))


def parse_chapter(
    content: str, *, words_per_minute: int = DEFAULT_WORDS_PER_MINUTE
) -> StoryChapter:
    """Parse ``content`` (JSON with ``title``/``content``) into a ``StoryChapter``.

    Tolerant of common LLM quirks: Markdown code fences, unescaped control
    characters in the long prose value (``strict=False``), and a JSON object
    that has itself been encoded as a JSON string (double-encoded).

    Raises:
        ChapterParseError: If the content is not valid JSON, is not an object,
            or the resulting chapter fails validation (e.g. empty fields). The
            message includes the underlying parse error for diagnosis.
    """
    try:
        data = loads_json(content, strict=False)
        if isinstance(data, str):  # some models double-encode the JSON as a string
            data = loads_json(data, strict=False)
    except json.JSONDecodeError as exc:
        raise ChapterParseError(
            f"invalid JSON from provider: {exc}", context={"error": str(exc)}
        ) from exc

    if not isinstance(data, dict):
        raise ChapterParseError(
            f"expected a JSON object for the chapter, got {type(data).__name__}"
        )

    title = str(data.get("title", ""))
    prose = str(data.get("content", ""))
    try:
        return StoryChapter(
            title=title,
            content=prose,
            estimated_duration_seconds=estimate_duration_seconds(
                prose, words_per_minute=words_per_minute
            ),
        )
    except ValidationError as exc:
        raise ChapterParseError(
            "chapter does not match schema", context={"error": str(exc)}
        ) from exc
