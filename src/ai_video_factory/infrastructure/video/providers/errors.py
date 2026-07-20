"""Error type for the video-generation provider layer.

Descends from the application's ``ProviderError`` so the whole system keeps a
single ``AppError`` root (docs/ai-tool.md §7). Concrete providers translate
their own failures into this type at the boundary; raw vendor or subprocess
exceptions never propagate outward.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ai_video_factory.errors import ProviderError


class VideoProviderError(ProviderError):
    """A video-generation provider failed to produce a clip."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, retryable=retryable, context=context)
