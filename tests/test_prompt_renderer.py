"""Tests for the Jinja2 prompt renderer."""

from __future__ import annotations

import pytest

from ai_video_factory.infrastructure.prompts.errors import (
    PromptRenderError,
    PromptValidationError,
)
from ai_video_factory.infrastructure.prompts.renderer import PromptRenderer


def test_render_substitutes_variables() -> None:
    renderer = PromptRenderer()
    variables = {"topic": "Tu tiên", "style": "Trung Quốc"}
    result = renderer.render("Topic {{ topic }} in {{ style }}", variables)
    assert result == "Topic Tu tiên in Trung Quốc"


def test_render_missing_variable_raises_render_error() -> None:
    renderer = PromptRenderer()
    with pytest.raises(PromptRenderError):
        renderer.render("Hello {{ name }}", {})


def test_render_invalid_syntax_raises_validation_error() -> None:
    renderer = PromptRenderer()
    with pytest.raises(PromptValidationError):
        renderer.render("Hello {{ name ", {"name": "x"})


def test_required_variables_sorted() -> None:
    renderer = PromptRenderer()
    assert renderer.required_variables("{{ topic }} {{ style }} {{ chapter }}") == [
        "chapter",
        "style",
        "topic",
    ]


def test_required_variables_invalid_syntax_raises() -> None:
    renderer = PromptRenderer()
    with pytest.raises(PromptValidationError):
        renderer.required_variables("{% for %}")
