"""Errors for the shot planner stage."""

from __future__ import annotations

from ai_video_factory.errors import InfrastructureError


class PlannerError(InfrastructureError):
    """A shot plan could not be produced, or a shot failed its own rules."""
