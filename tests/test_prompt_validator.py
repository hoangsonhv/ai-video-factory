"""Tests for the prompt validator."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_video_factory.infrastructure.prompts.errors import (
    PromptNotFoundError,
    PromptValidationError,
)
from ai_video_factory.infrastructure.prompts.loader import PromptLoader
from ai_video_factory.infrastructure.prompts.renderer import PromptRenderer
from ai_video_factory.infrastructure.prompts.validator import PromptValidator


def _validator(root: Path) -> PromptValidator:
    return PromptValidator(PromptLoader(root), PromptRenderer())


def _write(root: Path, name: str, text: str) -> None:
    path = root / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_validate_returns_required_variables(tmp_path: Path) -> None:
    _write(tmp_path, "story/idea", "{{ topic }} in {{ style }}")
    result = _validator(tmp_path).validate("story/idea")
    assert result.name == "story/idea"
    assert result.required_variables == ["style", "topic"]


def test_validate_missing_raises_not_found(tmp_path: Path) -> None:
    with pytest.raises(PromptNotFoundError):
        _validator(tmp_path).validate("story/missing")


def test_validate_invalid_syntax_raises(tmp_path: Path) -> None:
    _write(tmp_path, "broken", "{% if %}")
    with pytest.raises(PromptValidationError):
        _validator(tmp_path).validate("broken")


def test_validate_no_variables(tmp_path: Path) -> None:
    _write(tmp_path, "static", "no variables here")
    result = _validator(tmp_path).validate("static")
    assert result.required_variables == []
