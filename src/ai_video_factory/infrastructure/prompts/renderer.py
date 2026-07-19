"""Prompt renderer — renders template text with Jinja2.

Uses ``StrictUndefined`` so a missing variable is an explicit error rather than
a silent blank. Template syntax errors surface as :class:`PromptValidationError`
(the template is invalid); missing variables surface as :class:`PromptRenderError`
(the caller supplied the wrong inputs).
"""

from __future__ import annotations

from collections.abc import Mapping

from jinja2 import Environment, StrictUndefined, Template
from jinja2 import meta as jinja_meta
from jinja2.exceptions import TemplateSyntaxError, UndefinedError

from ai_video_factory.infrastructure.prompts.errors import (
    PromptRenderError,
    PromptValidationError,
)


class PromptRenderer:
    """Renders prompt templates and extracts their required variables."""

    def __init__(self) -> None:
        self._env: Environment = Environment(
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    def render(self, source: str, variables: Mapping[str, object]) -> str:
        """Render ``source`` with ``variables``.

        Raises:
            PromptValidationError: If the template syntax is invalid.
            PromptRenderError: If a required variable is missing.
        """
        try:
            template: Template = self._env.from_string(source)
        except TemplateSyntaxError as exc:
            raise PromptValidationError(f"invalid template syntax: {exc.message}") from exc
        try:
            rendered = template.render(**dict(variables))
        except UndefinedError as exc:
            raise PromptRenderError(
                f"missing prompt variable: {exc.message}"
            ) from exc

        return rendered

    def required_variables(self, source: str) -> list[str]:
        """Return the sorted variable names referenced by ``source``.

        Raises:
            PromptValidationError: If the template syntax is invalid.
        """
        try:
            ast = self._env.parse(source)
        except TemplateSyntaxError as exc:
            raise PromptValidationError(f"invalid template syntax: {exc.message}") from exc
        variables = jinja_meta.find_undeclared_variables(ast)  # type: ignore[no-untyped-call]
        return sorted(str(v) for v in variables)
