"""Image-prompt value object (domain layer).

A cinematic, provider-neutral specification for one image to be generated from
a story chapter. Pure and immutable (docs/ai-tool.md §2.1). Generating actual
images is out of scope for this stage.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ImagePrompt(BaseModel):
    """A single cinematic image-generation prompt for one visual."""

    model_config = ConfigDict(frozen=True)

    scene_number: int = Field(ge=1)
    prompt: str = Field(min_length=1)
    negative_prompt: str = ""
    aspect_ratio: str = Field(min_length=1)
    style: str = Field(min_length=1)
    camera: str = ""
    lighting: str = ""
    character_reference: str = ""
    environment: str = ""
    seed: int | None = None
