"""Prompt service — the façade the rest of the system uses for prompts.

Composes the loader, renderer, and validator behind three operations:
``render``, ``validate``, and ``list_prompts``.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ai_video_factory.infrastructure.prompts.loader import PromptLoader
from ai_video_factory.infrastructure.prompts.models import PromptValidation
from ai_video_factory.infrastructure.prompts.renderer import PromptRenderer
from ai_video_factory.infrastructure.prompts.validator import PromptValidator


class PromptService:
    """High-level entry point for loading, validating, and rendering prompts."""

    def __init__(
        self,
        loader: PromptLoader,
        renderer: PromptRenderer,
        validator: PromptValidator,
    ) -> None:
        self._loader = loader
        self._renderer = renderer
        self._validator = validator

    @classmethod
    def create(cls, root: Path) -> PromptService:
        """Build a service wired to the prompt templates under ``root``."""
        loader = PromptLoader(root)
        renderer = PromptRenderer()
        validator = PromptValidator(loader, renderer)
        return cls(loader, renderer, validator)

    def render(self, prompt_name: str, variables: Mapping[str, object]) -> str:
        """Render the named prompt with ``variables``."""
        source = self._loader.load(prompt_name)
        return self._renderer.render(source, variables)

    def validate(self, prompt_name: str) -> PromptValidation:
        """Validate the named prompt and return its required variables."""
        return self._validator.validate(prompt_name)

    def load(self, prompt_name: str) -> str:
        """Return the raw template text for ``prompt_name``."""
        return self._loader.load(prompt_name)

    def list_prompts(self) -> list[str]:
        """Return every available prompt name."""
        return self._loader.list_names()
