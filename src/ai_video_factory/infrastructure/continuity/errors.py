"""Errors for the visual continuity stage."""

from __future__ import annotations

from ai_video_factory.errors import InfrastructureError


class ContinuityError(InfrastructureError):
    """A visual context or continuity prompt could not be produced."""
