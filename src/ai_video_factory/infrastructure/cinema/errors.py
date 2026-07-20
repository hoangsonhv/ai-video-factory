"""Errors for the cinematic director stage."""

from __future__ import annotations

from ai_video_factory.errors import InfrastructureError


class CinemaError(InfrastructureError):
    """Cinematic direction could not be produced."""
