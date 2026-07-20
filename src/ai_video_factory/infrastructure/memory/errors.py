"""Errors for the character memory stage."""

from __future__ import annotations

from ai_video_factory.errors import InfrastructureError


class CharacterMemoryError(InfrastructureError):
    """A character memory could not be built, read, or applied."""
