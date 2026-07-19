"""Parse and validate the AI provider's JSON output into a ``StoryOutline``."""

from __future__ import annotations

import json

from pydantic import ValidationError

from ai_video_factory.domain.value_objects.outline import StoryOutline
from ai_video_factory.infrastructure.story.errors import OutlineParseError
from ai_video_factory.infrastructure.story.json_extract import loads_json


def parse_outline(content: str, *, expected_chapters: int) -> StoryOutline:
    """Parse ``content`` (JSON) into a validated :class:`StoryOutline`.

    Validates required fields and non-empty values (via the model) and that the
    number of chapter outlines matches ``expected_chapters``.

    Raises:
        OutlineParseError: If the content is not valid JSON, is not an object,
            fails schema validation, or has the wrong number of chapters.
    """
    try:
        data = loads_json(content)
    except json.JSONDecodeError as exc:
        raise OutlineParseError(
            "provider returned invalid JSON", context={"error": str(exc)}
        ) from exc

    if not isinstance(data, dict):
        raise OutlineParseError("expected a JSON object for the outline")

    try:
        outline = StoryOutline.model_validate(data)
    except ValidationError as exc:
        raise OutlineParseError(
            "outline does not match schema", context={"error": str(exc)}
        ) from exc

    actual = len(outline.chapter_outlines)
    if actual != expected_chapters:
        raise OutlineParseError(
            f"expected {expected_chapters} chapters but got {actual}",
            context={"expected": expected_chapters, "actual": actual},
        )
    return outline
