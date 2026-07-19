"""Tests for the ``ai-video-factory chapter`` CLI command (no real API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.infrastructure.providers.base.models import (
    LLMRequest,
    LLMResponse,
    TokenUsage,
)
from ai_video_factory.infrastructure.story import chapter_generator as cg
from ai_video_factory.interface.cli.app import app

runner = CliRunner()
_CHAPTER = json.dumps({"title": "Chapter One", "content": " ".join(["word"] * 300)})


def _outline_json() -> str:
    return json.dumps(
        {
            "title": "T",
            "genre": "xianxia",
            "world_setting": "W",
            "cultivation_system": "C",
            "main_character": "M",
            "supporting_characters": ["A"],
            "antagonist": "X",
            "story_arc": "arc",
            "ending": "end",
            "chapter_outlines": [
                {"chapter_number": 1, "title": "C1", "summary": "s", "cliffhanger": "!"}
            ],
        }
    )


class _FakeProvider:
    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content=_CHAPTER,
            finish_reason="STOP",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            provider="fake",
            model="fake",
            latency=0.0,
        )


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_PROMPTS__ROOT", str(Path(__file__).resolve().parents[1] / "prompts"))
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))


def test_chapter_command_generates_and_saves(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cg.ProviderFactory, "create", lambda settings=None: _FakeProvider())
    outline_path = tmp_path / "story_outline.json"
    outline_path.write_text(_outline_json(), encoding="utf-8")

    result = runner.invoke(app, ["chapter", "--outline", str(outline_path)])

    assert result.exit_code == 0
    assert "Chapter One" in result.stdout
    out_file = tmp_path / "out" / "chapter.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["title"] == "Chapter One"
    assert data["estimated_duration_seconds"] == 120  # 300 words at 150 wpm


def test_chapter_command_missing_outline_fails(tmp_path: Path) -> None:
    result = runner.invoke(app, ["chapter", "--outline", str(tmp_path / "nope.json")])
    assert result.exit_code == 1
