"""Errors for the AI Director stage."""

from __future__ import annotations

from ai_video_factory.errors import InfrastructureError


class DirectorError(InfrastructureError):
    """A shot plan could not be produced, read, or applied."""
