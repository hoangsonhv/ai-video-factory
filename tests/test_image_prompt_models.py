"""Tests for the image-prompt domain value object."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt


def test_valid_image_prompt_with_defaults() -> None:
    image = ImagePrompt(
        scene_number=1, prompt="a lone cultivator", aspect_ratio="9:16", style="cinematic"
    )
    assert image.negative_prompt == ""
    assert image.camera == ""
    assert image.seed is None


def test_image_prompt_is_frozen() -> None:
    image = ImagePrompt(scene_number=1, prompt="p", aspect_ratio="9:16", style="cinematic")
    with pytest.raises(ValidationError):
        image.prompt = "x"  # type: ignore[misc]


def test_scene_number_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        ImagePrompt(scene_number=0, prompt="p", aspect_ratio="9:16", style="cinematic")


def test_empty_prompt_raises() -> None:
    with pytest.raises(ValidationError):
        ImagePrompt(scene_number=1, prompt="", aspect_ratio="9:16", style="cinematic")


def test_optional_seed_accepts_int() -> None:
    image = ImagePrompt(scene_number=1, prompt="p", aspect_ratio="9:16", style="cinematic", seed=42)
    assert image.seed == 42
