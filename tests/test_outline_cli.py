"""Tests for the ``ai-video-factory outline`` CLI command (no real API)."""

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
from ai_video_factory.infrastructure.story import outline_generator as og
from ai_video_factory.interface.cli.app import app

runner = CliRunner()


def _outline_json(chapters: int) -> str:
    return json.dumps(
        {
            "title": "Outline",
            "genre": "xianxia",
            "world_setting": "W",
            "cultivation_system": "C",
            "main_character": "M",
            "supporting_characters": ["A", "B"],
            "antagonist": "X",
            "story_arc": "arc",
            "ending": "end",
            "chapter_outlines": [
                {"chapter_number": i, "title": f"C{i}", "summary": "s", "cliffhanger": "!"}
                for i in range(1, chapters + 1)
            ],
        }
    )


class _FakeProvider:
    def __init__(self, chapters: int) -> None:
        self._content = _outline_json(chapters)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content=self._content,
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


def _write_ideas(path: Path) -> None:
    path.write_text(
        json.dumps({"ideas": [{"title": "T", "hook": "H", "summary": "S", "tags": ["a"]}]}),
        encoding="utf-8",
    )


def test_outline_command_generates_and_saves(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(og.ProviderFactory, "create", lambda settings=None: _FakeProvider(3))
    ideas_path = tmp_path / "ideas.json"
    _write_ideas(ideas_path)

    result = runner.invoke(
        app, ["outline", "--idea", str(ideas_path), "--index", "0", "--chapters", "3"]
    )

    assert result.exit_code == 0
    assert "Outline" in result.stdout
    out_file = tmp_path / "out" / "story_outline.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert len(data["chapter_outlines"]) == 3


def test_outline_command_missing_ideas_file_fails(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["outline", "--idea", str(tmp_path / "nope.json"), "--chapters", "3"]
    )
    assert result.exit_code == 1
