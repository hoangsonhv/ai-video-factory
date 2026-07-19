"""Models for the asset pipeline (infrastructure).

``AssetResult`` is the uniform result every asset generator returns; ``AssetStage``
describes the readiness of a pipeline stage for the ``assets`` status view.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class AssetResult(BaseModel):
    """The uniform result of generating one asset (images, voice, subtitles, video)."""

    model_config = ConfigDict(frozen=True)

    success: bool
    path: Path | None = None
    duration: float = Field(default=0.0, ge=0.0)
    metadata: Mapping[str, object] = Field(default_factory=dict)


class AssetStage(BaseModel):
    """Readiness of a single pipeline stage, for the status view."""

    model_config = ConfigDict(frozen=True)

    name: str
    backend: str
    ready: bool
