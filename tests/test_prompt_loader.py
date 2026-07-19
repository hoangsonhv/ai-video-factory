"""Tests for the prompt loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_video_factory.infrastructure.prompts.errors import PromptNotFoundError
from ai_video_factory.infrastructure.prompts.loader import PromptLoader


def _write(root: Path, name: str, text: str) -> None:
    path = root / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_load_returns_file_contents(tmp_path: Path) -> None:
    _write(tmp_path, "story/idea", "Idea: {{ topic }}")
    loader = PromptLoader(tmp_path)
    assert loader.load("story/idea") == "Idea: {{ topic }}"


def test_load_caches_content(tmp_path: Path) -> None:
    _write(tmp_path, "story/idea", "first")
    loader = PromptLoader(tmp_path)
    assert loader.load("story/idea") == "first"
    (tmp_path / "story" / "idea.md").write_text("second", encoding="utf-8")
    assert loader.load("story/idea") == "first"  # served from cache


def test_load_missing_raises(tmp_path: Path) -> None:
    loader = PromptLoader(tmp_path)
    with pytest.raises(PromptNotFoundError):
        loader.load("story/missing")


def test_load_rejects_path_traversal(tmp_path: Path) -> None:
    loader = PromptLoader(tmp_path)
    with pytest.raises(PromptNotFoundError):
        loader.load("../secret")


def test_list_names_sorted_posix(tmp_path: Path) -> None:
    _write(tmp_path, "story/idea", "x")
    _write(tmp_path, "image/image_prompt", "y")
    loader = PromptLoader(tmp_path)
    assert loader.list_names() == ["image/image_prompt", "story/idea"]


def test_list_names_empty_when_root_missing(tmp_path: Path) -> None:
    loader = PromptLoader(tmp_path / "does-not-exist")
    assert loader.list_names() == []
