"""Tests for the image-prompt JSON parser."""

from __future__ import annotations

import json

import pytest

from ai_video_factory.infrastructure.story.errors import ImagePromptParseError
from ai_video_factory.infrastructure.story.image_prompt_parser import parse_image_prompts

_ITEM = {
    "scene_number": 1,
    "prompt": "a lone cultivator on a cliff",
    "negative_prompt": "blurry, watermark",
    "camera": "wide shot",
    "lighting": "golden hour",
    "character_reference": "young man in white robe",
    "environment": "misty mountain peak",
    "seed": None,
}


def test_parse_object_with_key_injects_style_and_aspect() -> None:
    content = json.dumps({"image_prompts": [_ITEM, {**_ITEM, "scene_number": 2}]})
    prompts = parse_image_prompts(content, style="cinematic", aspect_ratio="9:16")
    assert len(prompts) == 2
    assert prompts[0].style == "cinematic"
    assert prompts[0].aspect_ratio == "9:16"
    assert prompts[1].scene_number == 2


def test_style_and_aspect_override_model_values() -> None:
    item = {**_ITEM, "style": "wrong", "aspect_ratio": "16:9"}
    prompts = parse_image_prompts(json.dumps([item]), style="cinematic", aspect_ratio="9:16")
    assert prompts[0].style == "cinematic"
    assert prompts[0].aspect_ratio == "9:16"


def test_invalid_json_raises() -> None:
    with pytest.raises(ImagePromptParseError):
        parse_image_prompts("not json", style="cinematic", aspect_ratio="9:16")


def test_missing_prompt_field_raises() -> None:
    bad = {"scene_number": 1, "camera": "wide"}
    with pytest.raises(ImagePromptParseError):
        parse_image_prompts(json.dumps([bad]), style="cinematic", aspect_ratio="9:16")


def test_empty_list_raises() -> None:
    with pytest.raises(ImagePromptParseError):
        parse_image_prompts(json.dumps({"image_prompts": []}), style="c", aspect_ratio="9:16")
