"""Parse the AI provider's JSON output into validated ``ImagePrompt`` models.

The project-level ``style`` and ``aspect_ratio`` are injected onto every prompt
for consistency; the model supplies only the creative fields.
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.infrastructure.story.errors import ImagePromptParseError
from ai_video_factory.infrastructure.story.json_extract import loads_json


def parse_image_prompts(content: str, *, style: str, aspect_ratio: str) -> list[ImagePrompt]:
    """Parse ``content`` (JSON) into a validated list of image prompts.

    Accepts either a top-level array or an object with an ``"image_prompts"``
    array. ``style`` and ``aspect_ratio`` are injected onto each prompt.

    Raises:
        ImagePromptParseError: If the content is not valid JSON, is not shaped
            as a list, or an item fails schema validation.
    """
    try:
        data = loads_json(content)
    except json.JSONDecodeError as exc:
        raise ImagePromptParseError(
            "provider returned invalid JSON", context={"error": str(exc)}
        ) from exc

    raw = data.get("image_prompts", []) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        raise ImagePromptParseError("expected a JSON array of image prompts")

    prompts: list[ImagePrompt] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ImagePromptParseError("each image prompt must be a JSON object")
        merged = {**item, "style": style, "aspect_ratio": aspect_ratio}
        try:
            prompts.append(ImagePrompt.model_validate(merged))
        except ValidationError as exc:
            raise ImagePromptParseError(
                "image prompt does not match schema", context={"error": str(exc)}
            ) from exc

    if not prompts:
        raise ImagePromptParseError("provider returned no image prompts")
    return prompts
