"""Integration tests for the pipeline runner and the ``generate`` CLI.

A single stage-aware fake provider returns the right JSON for each stage
(keyed on the request's ``stage`` metadata), so the whole idea → outline →
chapter → image-prompts pipeline runs with no real API calls.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.infrastructure.pipeline import runner as runner_module
from ai_video_factory.infrastructure.pipeline.models import PipelineRequest
from ai_video_factory.infrastructure.pipeline.runner import PipelineRunner
from ai_video_factory.infrastructure.providers.base.models import (
    LLMRequest,
    LLMResponse,
    ProviderHealth,
    TokenUsage,
)
from ai_video_factory.infrastructure.story.errors import ChapterParseError
from ai_video_factory.interface.cli.app import app
from ai_video_factory.shared.health import HealthStatus

_REPO_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
runner = CliRunner()


def _ideas_json() -> str:
    return json.dumps(
        {
            "ideas": [
                {"title": f"Idea {i}", "hook": "H", "summary": "S", "tags": ["a"]}
                for i in range(10)
            ]
        }
    )


def _outline_json(chapters: int) -> str:
    return json.dumps(
        {
            "title": "Tu Tiên Ký",
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


def _chapter_json() -> str:
    return json.dumps({"title": "Chapter", "content": " ".join(["từ"] * 120)})


def _image_prompts_json(count: int) -> str:
    return json.dumps(
        {
            "image_prompts": [
                {"scene_number": i, "prompt": f"visual {i}", "camera": "wide"}
                for i in range(1, count + 1)
            ]
        }
    )


class StageAwareFakeProvider:
    """Returns stage-appropriate JSON based on ``request.metadata['stage']``."""

    def __init__(
        self, *, chapters: int = 3, images: int = 2, fail_stage: str | None = None
    ) -> None:
        self._chapters = chapters
        self._images = images
        self._fail_stage = fail_stage
        self.stages: list[str] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        stage = str(request.metadata.get("stage", ""))
        self.stages.append(stage)
        if stage == self._fail_stage:
            content = "not json"
        elif stage == "idea":
            content = _ideas_json()
        elif stage == "outline":
            content = _outline_json(self._chapters)
        elif stage == "chapter":
            content = _chapter_json()
        elif stage == "image_prompt":
            content = _image_prompts_json(self._images)
        else:
            content = "{}"
        return LLMResponse(
            content=content,
            finish_reason="STOP",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            provider="fake",
            model="fake",
            latency=0.0,
        )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(status=HealthStatus.OK, detail="fake")

    async def count_tokens(self, text: str, *, model: str | None = None) -> int:
        return 0

    async def models(self) -> list[str]:
        return ["fake"]


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_PROMPTS__ROOT", str(_REPO_PROMPTS))
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))


_OUTPUT_FILES = ["ideas.json", "story_outline.json", "chapter.json", "image_prompts.json"]


def test_runner_produces_all_outputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = StageAwareFakeProvider(chapters=3, images=2)
    monkeypatch.setattr(runner_module.ProviderFactory, "create", lambda settings: fake)
    pipeline = PipelineRunner.from_settings(load_settings())
    request = PipelineRequest(
        topic="Tu tiên",
        style="Trung Quốc",
        target_platform="tiktok",
        chapter_count=3,
        image_count=2,
    )

    result = asyncio.run(pipeline.run(request))

    out = tmp_path / "out"
    for name in _OUTPUT_FILES:
        assert (out / name).exists()
    assert fake.stages == ["idea", "outline", "chapter", "image_prompt"]
    assert len(result.ideas) == 10
    assert len(result.outline.chapter_outlines) == 3
    assert len(result.image_prompts) == 2
    assert result.outputs == [out / name for name in _OUTPUT_FILES]


def test_runner_stops_on_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = StageAwareFakeProvider(chapters=3, fail_stage="chapter")
    monkeypatch.setattr(runner_module.ProviderFactory, "create", lambda settings: fake)
    pipeline = PipelineRunner.from_settings(load_settings())
    request = PipelineRequest(
        topic="Tu tiên", style="Trung Quốc", target_platform="tiktok", chapter_count=3
    )

    with pytest.raises(ChapterParseError):
        asyncio.run(pipeline.run(request))

    out = tmp_path / "out"
    assert (out / "ideas.json").exists()
    assert (out / "story_outline.json").exists()
    assert not (out / "chapter.json").exists()
    assert not (out / "image_prompts.json").exists()
    assert fake.stages == ["idea", "outline", "chapter", "chapter"]  # one retry, then stop


def test_generate_cli_runs_full_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = StageAwareFakeProvider(chapters=3, images=2)
    monkeypatch.setattr(runner_module.ProviderFactory, "create", lambda settings: fake)

    result = runner.invoke(
        app,
        [
            "generate",
            "--topic",
            "Tu tiên",
            "--style",
            "Trung Quốc",
            "--platform",
            "tiktok",
            "--chapters",
            "3",
        ],
    )

    assert result.exit_code == 0
    out = tmp_path / "out"
    for name in _OUTPUT_FILES:
        assert (out / name).exists()
