"""Vendor-neutral request/response models for the image provider layer."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ImageGenerationRequest(BaseModel):
    """A single image-generation request, independent of any provider."""

    model_config = ConfigDict(frozen=True)

    prompt: str = Field(min_length=1)
    negative_prompt: str = ""
    aspect_ratio: str = "9:16"
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    seed: int | None = None
    style: str = ""
    provider_options: Mapping[str, object] = Field(default_factory=dict)


class ImageGenerationResponse(BaseModel):
    """The result of generating (and saving) one image."""

    model_config = ConfigDict(frozen=True)

    image_path: Path
    provider: str
    model: str
    generation_time: float = Field(ge=0.0)
    metadata: Mapping[str, object] = Field(default_factory=dict)
