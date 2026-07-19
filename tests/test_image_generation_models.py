"""Tests for the image generation request/response models."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_video_factory.infrastructure.providers.image.base.models import (
    ImageGenerationRequest,
    ImageGenerationResponse,
)


def test_request_defaults() -> None:
    request = ImageGenerationRequest(prompt="a lone cultivator")
    assert request.aspect_ratio == "9:16"
    assert request.negative_prompt == ""
    assert request.width is None
    assert request.seed is None
    assert dict(request.provider_options) == {}


def test_request_is_frozen() -> None:
    request = ImageGenerationRequest(prompt="p")
    with pytest.raises(ValidationError):
        request.prompt = "x"  # type: ignore[misc]


def test_request_requires_non_empty_prompt() -> None:
    with pytest.raises(ValidationError):
        ImageGenerationRequest(prompt="")


def test_response_fields() -> None:
    response = ImageGenerationResponse(
        image_path=Path("output/images/image_001.png"),
        provider="gemini_imagen",
        model="imagen-3.0",
        generation_time=1.5,
    )
    assert response.image_path.name == "image_001.png"
    assert response.provider == "gemini_imagen"
    assert dict(response.metadata) == {}
