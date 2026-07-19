"""Error hierarchy for the prompt engine.

These extend the application's infrastructure ``InfrastructureError`` so the
whole system keeps a single ``AppError`` root (docs/ai-tool.md §7).
"""

from __future__ import annotations

from ai_video_factory.errors import InfrastructureError


class PromptError(InfrastructureError):
    """Base class for any prompt-engine failure."""


class PromptNotFoundError(PromptError):
    """The requested prompt template does not exist under the prompt root."""


class PromptValidationError(PromptError):
    """A prompt template is invalid (e.g. malformed template syntax)."""


class PromptRenderError(PromptError):
    """A prompt could not be rendered (e.g. a required variable was missing)."""
