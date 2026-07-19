"""Tests for the ``ai-video-factory image`` CLI command (no real API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.infrastructure.media.image_storage import ImageStorage
from ai_video_factory.infrastructure.providers.image.base.models import (
    ImageGenerationRequest,
    ImageGenerationResponse,
)
from ai_video_factory.interface.cli import image_commands as ic
from ai_video_factory.interface.cli.app import app

runner = CliRunner()


class _FakeImageProvider:
    """Uses the real storage to actually save bytes, so files are produced."""

    def __init__(self, storage: ImageStorage) -> None:
        self._storage = storage

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        path = self._storage.save(b"FAKEPNG")
        return ImageGenerationResponse(
            image_path=path, provider="fake", model="fake", generation_time=0.0
        )


def _image_prompts_json(count: int) -> str:
    return json.dumps(
        {
            "image_prompts": [
                {
                    "scene_number": i,
                    "prompt": f"visual {i}",
                    "aspect_ratio": "9:16",
                    "style": "cinematic",
                }
                for i in range(1, count + 1)
            ]
        }
    )


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))


def test_image_command_generates_and_saves(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        ic.ImageProviderFactory, "create", lambda settings, storage: _FakeImageProvider(storage)
    )
    prompts_path = tmp_path / "image_prompts.json"
    prompts_path.write_text(_image_prompts_json(3), encoding="utf-8")

    result = runner.invoke(app, ["image", "--input", str(prompts_path)])

    assert result.exit_code == 0
    images_dir = tmp_path / "out" / "images"
    assert (images_dir / "image_001.png").exists()
    assert (images_dir / "image_002.png").exists()
    assert (images_dir / "image_003.png").exists()
    assert (images_dir / "image_001.png").read_bytes() == b"FAKEPNG"


def test_image_command_missing_input_fails(tmp_path: Path) -> None:
    result = runner.invoke(app, ["image", "--input", str(tmp_path / "nope.json")])
    assert result.exit_code == 1
