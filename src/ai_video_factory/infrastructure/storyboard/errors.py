"""Errors for the storyboard stage."""

from __future__ import annotations

from ai_video_factory.errors import InfrastructureError


class StoryboardError(InfrastructureError):
    """A storyboard could not be built, read, or written."""
