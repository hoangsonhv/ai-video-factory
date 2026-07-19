"""Parse and validate the AI provider's JSON output into ``StoryIdea`` models."""

from __future__ import annotations

import json

from pydantic import ValidationError

from ai_video_factory.domain.value_objects.idea import StoryIdea
from ai_video_factory.infrastructure.story.errors import IdeaParseError
from ai_video_factory.infrastructure.story.json_extract import loads_json


def parse_ideas(content: str) -> list[StoryIdea]:
    """Parse ``content`` (JSON) into a validated list of story ideas.

    Accepts either a top-level JSON array of ideas or an object with an
    ``"ideas"`` array.

    Raises:
        IdeaParseError: If the content is not valid JSON, is not shaped as a
            list of ideas, or an idea fails schema validation.
    """
    try:
        data = loads_json(content)
    except json.JSONDecodeError as exc:
        raise IdeaParseError("provider returned invalid JSON", context={"error": str(exc)}) from exc

    raw = data.get("ideas", []) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        raise IdeaParseError("expected a JSON array of ideas")

    ideas: list[StoryIdea] = []
    for item in raw:
        try:
            ideas.append(StoryIdea.model_validate(item))
        except ValidationError as exc:
            raise IdeaParseError("idea does not match schema", context={"error": str(exc)}) from exc

    if not ideas:
        raise IdeaParseError("provider returned no ideas")
    return ideas
