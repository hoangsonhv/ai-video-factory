"""Tests for the asset pipeline foundation (models, adapters, runner, CLI)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.domain.value_objects.chapter import StoryChapter
from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.infrastructure.asset_pipeline.adapters import (
    ImageAssetGenerator,
    SpeechAssetGenerator,
)
from ai_video_factory.infrastructure.asset_pipeline.errors import AssetStageUnavailableError
from ai_video_factory.infrastructure.asset_pipeline.models import AssetResult
from ai_video_factory.infrastructure.asset_pipeline.runner import AssetPipelineRunner
from ai_video_factory.infrastructure.media.audio_storage import AudioStorage
from ai_video_factory.infrastructure.media.image_storage import ImageStorage
from ai_video_factory.infrastructure.providers.image.base.models import (
    ImageGenerationRequest,
    ImageGenerationResponse,
)
from ai_video_factory.infrastructure.providers.speech.base.models import (
    SpeechSynthesisRequest,
    SpeechSynthesisResponse,
)
from ai_video_factory.interface.cli.app import app

runner = CliRunner()


class _FakeImageProvider:
    def __init__(self, storage: ImageStorage) -> None:
        self._storage = storage

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        path = self._storage.save(b"PNG")
        return ImageGenerationResponse(
            image_path=path, provider="fake", model="fake", generation_time=0.0
        )


class _FakeSpeechProvider:
    def __init__(self, storage: AudioStorage) -> None:
        self._storage = storage

    async def synthesize(self, request: SpeechSynthesisRequest) -> SpeechSynthesisResponse:
        path = self._storage.save(b"WAV")
        return SpeechSynthesisResponse(
            audio_path=path, provider="fake", voice="Kore", duration_seconds=4.2, sample_rate=24000
        )


def _prompts(count: int) -> list[ImagePrompt]:
    return [
        ImagePrompt(scene_number=i, prompt=f"visual {i}", aspect_ratio="9:16", style="cinematic")
        for i in range(1, count + 1)
    ]


def _chapter() -> StoryChapter:
    return StoryChapter(title="T", content="Xin chào", estimated_duration_seconds=5)


# --- AssetResult model ---


def test_asset_result_defaults() -> None:
    result = AssetResult(success=True)
    assert result.path is None
    assert result.duration == 0.0
    assert dict(result.metadata) == {}


# --- Adapters (wrap the real providers) ---


def test_image_asset_generator_produces_result(tmp_path: Path) -> None:
    storage = ImageStorage(tmp_path / "images")
    generator = ImageAssetGenerator(_FakeImageProvider(storage), storage)

    result = asyncio.run(generator.generate_images(_prompts(3)))

    assert result.success is True
    assert result.path == storage.directory
    assert result.metadata["count"] == 3
    assert (storage.directory / "image_001.png").exists()


def test_speech_asset_generator_produces_result(tmp_path: Path) -> None:
    storage = AudioStorage(tmp_path / "audio")
    generator = SpeechAssetGenerator(_FakeSpeechProvider(storage))

    result = asyncio.run(generator.generate_voice(_chapter()))

    assert result.success is True
    assert result.path is not None and result.path.name == "narration.mp3"
    assert result.duration == 4.2


# --- Runner orchestration ---


def _runner(tmp_path: Path) -> AssetPipelineRunner:
    image_storage = ImageStorage(tmp_path / "images")
    audio_storage = AudioStorage(tmp_path / "audio")
    return AssetPipelineRunner(
        ImageAssetGenerator(_FakeImageProvider(image_storage), image_storage),
        SpeechAssetGenerator(_FakeSpeechProvider(audio_storage)),
    )


def test_runner_generates_images_and_voice(tmp_path: Path) -> None:
    pipeline = _runner(tmp_path)
    images = asyncio.run(pipeline.generate_images(_prompts(2)))
    voice = asyncio.run(pipeline.generate_voice(_chapter()))
    assert images.metadata["count"] == 2
    assert voice.duration == 4.2


def test_runner_subtitles_unavailable(tmp_path: Path) -> None:
    pipeline = _runner(tmp_path)
    with pytest.raises(AssetStageUnavailableError):
        asyncio.run(pipeline.generate_subtitles(_chapter()))


def test_runner_video_unavailable(tmp_path: Path) -> None:
    pipeline = _runner(tmp_path)
    dummy = AssetResult(success=True)
    with pytest.raises(AssetStageUnavailableError):
        asyncio.run(pipeline.compose_video(dummy, dummy, dummy))


def test_runner_stage_status(tmp_path: Path) -> None:
    stages = {s.name: s.ready for s in _runner(tmp_path).stage_status()}
    assert stages == {"images": True, "voice": True, "subtitles": False, "video": False}


# --- CLI status ---


def test_assets_cli_shows_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVF_LOGGING__FILE_ENABLED", "false")
    monkeypatch.setenv("AIVF_APP__OUTPUT_DIR", str(tmp_path / "out"))

    result = runner.invoke(app, ["assets"])

    assert result.exit_code == 0
    assert "images" in result.stdout
    assert "video" in result.stdout
    assert "pending" in result.stdout
