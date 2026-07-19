"""Prompt validator — checks that a template exists, parses, and its variables.

Validation confirms the three properties required by the prompt engine: the
file exists (delegated to the loader), the Jinja2 syntax is valid, and the set
of required variables can be determined.
"""

from __future__ import annotations

from ai_video_factory.infrastructure.prompts.loader import PromptLoader
from ai_video_factory.infrastructure.prompts.models import PromptValidation
from ai_video_factory.infrastructure.prompts.renderer import PromptRenderer


class PromptValidator:
    """Validates prompt templates using the loader and renderer."""

    def __init__(self, loader: PromptLoader, renderer: PromptRenderer) -> None:
        self._loader = loader
        self._renderer = renderer

    def validate(self, name: str) -> PromptValidation:
        """Validate the prompt ``name`` and return its required variables.

        Raises:
            PromptNotFoundError: If the template file does not exist.
            PromptValidationError: If the template syntax is invalid.
        """
        source = self._loader.load(name)
        required = self._renderer.required_variables(source)
        return PromptValidation(name=name, required_variables=required)
