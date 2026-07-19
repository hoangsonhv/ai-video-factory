"""Errors for the story-idea and story-outline generation services."""

from __future__ import annotations

from ai_video_factory.errors import InfrastructureError


class IdeaParseError(InfrastructureError):
    """The AI provider returned output that could not be parsed into ideas."""


class OutlineParseError(InfrastructureError):
    """The AI provider returned output that could not be parsed into an outline."""


class ChapterParseError(InfrastructureError):
    """The AI provider returned output that could not be parsed into a chapter."""


class ImagePromptParseError(InfrastructureError):
    """The AI provider returned output that could not be parsed into image prompts."""
