"""Lenient JSON parsing for LLM output.

Providers configured for JSON mode should return raw JSON, but some models wrap
their output in Markdown code fences. This strips a surrounding ```` ``` ````/
```` ```json ```` fence before parsing so the structured stages are robust to it.
"""

from __future__ import annotations

import json


def loads_json(content: str, *, strict: bool = True) -> object:
    """Parse JSON from ``content``, tolerating surrounding Markdown code fences.

    Args:
        content: The raw text that should contain JSON.
        strict: When ``False``, literal control characters (e.g. newlines) are
            allowed inside strings — useful for long prose values that some
            models emit without escaping.

    Raises:
        json.JSONDecodeError: If the de-fenced content is not valid JSON.
    """
    text = content.strip()
    if text.startswith("```"):
        newline = text.find("\n")
        text = text[newline + 1 :] if newline != -1 else text[3:]
        trimmed = text.rstrip()
        if trimmed.endswith("```"):
            text = trimmed[:-3]
    result: object = json.loads(text.strip(), strict=strict)
    return result
