"""Tests for the ``ai-video-factory idea`` CLI command (no real API)."""

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
from ai_video_factory.infrastructure.story import idea_generator as ig
from ai_video_factory.interface.cli.app import app

runner = CliRunner()
_REPO_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
_IDEAS = json.dumps(
    {"ideas": [{"title": f"T{i}", "hook": "H", "summary": "S", "tags": ["a"]} for i in range(10)]}
)


class _FakeProvider:
    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content=_IDEAS,
            finish_reason="STOP",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            provider="fake",
            model="fake",
            latency=0.0,
        )


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_PROMPTS__ROOT", str(_REPO_PROMPTS))
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))


def test_idea_command_generates_and_saves(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ig.ProviderFactory, "create", lambda settings=None: _FakeProvider())

    result = runner.invoke(
        app, ["idea", "--topic", "Tu tiên", "--style", "Trung Quốc", "--platform", "tiktok"]
    )

    assert result.exit_code == 0
    assert "T0" in result.stdout
    out_file = tmp_path / "out" / "ideas.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert len(data["ideas"]) == 10
    assert data["brief"]["target_platform"] == "tiktok"


def test_idea_command_fails_without_api_key() -> None:
    # No provider monkeypatch and no API key -> GeminiProvider raises
    # AuthenticationError (no real network call), surfaced as exit code 1.
    result = runner.invoke(app, ["idea", "--topic", "x", "--style", "y", "--platform", "tiktok"])
    assert result.exit_code == 1
