"""Errors for the asset pipeline."""

from __future__ import annotations

from ai_video_factory.errors import InfrastructureError


class AssetStageUnavailableError(InfrastructureError):
    """A requested asset stage has no generator wired yet (a future sprint)."""
