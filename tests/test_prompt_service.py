"""Tests for the prompt service, including the shipped prompt templates."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_video_factory.infrastructure.prompts.errors import PromptNotFoundError
from ai_video_factory.infrastructure.prompts.service import PromptService

_REPO_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


def _write(root: Path, name: str, text: str) -> None:
    path = root / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_render_validate_and_list(tmp_path: Path) -> None:
    _write(tmp_path, "story/idea", "Topic: {{ topic }} ({{ style }})")
    _write(tmp_path, "image/image_prompt", "Scene: {{ scene }}")
    service = PromptService.create(tmp_path)

    assert service.list_prompts() == ["image/image_prompt", "story/idea"]
    assert service.render("story/idea", {"topic": "Tu tiên", "style": "Trung Quốc"}) == (
        "Topic: Tu tiên (Trung Quốc)"
    )
    assert service.validate("story/idea").required_variables == ["style", "topic"]


def test_render_missing_prompt_raises(tmp_path: Path) -> None:
    service = PromptService.create(tmp_path)
    with pytest.raises(PromptNotFoundError):
        service.render("nope", {})


def test_shipped_prompts_exist_and_validate() -> None:
    service = PromptService.create(_REPO_PROMPTS)
    names = service.list_prompts()
    assert {
        "story/idea",
        "story/outline",
        "story/chapter",
        "story/scene",
        "image/image_prompt",
    } <= set(names)
    for name in names:
        service.validate(name)  # raises if any shipped template is invalid


def test_shipped_idea_renders_with_example_variables() -> None:
    service = PromptService.create(_REPO_PROMPTS)
    # The `factory prompt render story/idea --var topic=... --var style=...`
    # example must succeed under StrictUndefined, so idea.md uses exactly these.
    assert service.validate("story/idea").required_variables == ["style", "topic"]
    rendered = service.render("story/idea", {"topic": "Tu tiên", "style": "Trung Quốc"})
    assert "Tu tiên" in rendered
    assert "Trung Quốc" in rendered
