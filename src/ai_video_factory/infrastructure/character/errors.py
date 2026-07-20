"""Errors for the character consistency services."""

from __future__ import annotations

from ai_video_factory.errors import InfrastructureError


class CharacterLibraryError(InfrastructureError):
    """A character library could not be built, read, or applied."""
