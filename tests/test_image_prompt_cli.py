"""Tests for the ``ai-video-factory image-prompt`` CLI command (no real API)."""

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
from ai_video_factory.infrastructure.story import image_prompt_generator as ipg
from ai_video_factory.interface.cli.app import app

runner = CliRunner()


def _prompts_json(count: int) -> str:
    return json.dumps(
        {
            "image_prompts": [
                {
                    "scene_number": i,
                    "prompt": f"visual {i}",
                    "negative_prompt": "blurry",
                    "camera": "wide",
                    "lighting": "golden hour",
                    "character_reference": "cultivator",
                    "environment": "mountain",
                    "seed": None,
                }
                for i in range(1, count + 1)
            ]
        }
    )


class _FakeProvider:
    def __init__(self, count: int) -> None:
        self._content = _prompts_json(count)

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


def test_image_prompt_command_generates_and_saves(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ipg.ProviderFactory, "create", lambda settings=None: _FakeProvider(4))
    chapter_path = tmp_path / "chapter.json"
    chapter_path.write_text(
        json.dumps({"title": "T", "content": "prose", "estimated_duration_seconds": 30}),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["image-prompt", "--chapter", str(chapter_path), "--count", "4"])

    assert result.exit_code == 0
    assert "visual 1" in result.stdout
    out_file = tmp_path / "out" / "image_prompts.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert len(data["image_prompts"]) == 4
    assert data["image_prompts"][0]["aspect_ratio"] == "9:16"


def test_image_prompt_command_missing_chapter_fails(tmp_path: Path) -> None:
    result = runner.invoke(app, ["image-prompt", "--chapter", str(tmp_path / "nope.json")])
    assert result.exit_code == 1
