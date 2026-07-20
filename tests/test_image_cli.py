"""Tests for the ``ai-video-factory image`` CLI command (no real API)."""

from __future__ import annotations

import asyncio
import json
import struct
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_video_factory.infrastructure.config.settings import ImageProviderSettings
from ai_video_factory.infrastructure.media.image_storage import ImageStorage
from ai_video_factory.infrastructure.providers.base.errors import ProviderUnavailableError
from ai_video_factory.infrastructure.providers.image.base.models import (
    ImageGenerationRequest,
    ImageGenerationResponse,
)
from ai_video_factory.infrastructure.providers.image.pollinations.provider import (
    PollinationsImageProvider,
)
from ai_video_factory.interface.cli import image_commands as ic
from ai_video_factory.interface.cli.app import app

runner = CliRunner()

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_bytes(width: int, height: int) -> bytes:
    """A minimal PNG whose IHDR carries the given dimensions (enough to parse)."""
    return (
        _PNG_SIGNATURE
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
        + b"\x00" * 16
    )


class _FakeImageProvider:
    """Saves real bytes via a storage; can fail on chosen generate-call numbers."""

    def __init__(
        self,
        storage: ImageStorage,
        *,
        content: bytes = _png_bytes(64, 96),
        fail_calls: set[int] | None = None,
    ) -> None:
        self._storage = storage
        self._content = content
        self._fail = fail_calls or set()
        self.calls = 0

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        self.calls += 1
        if self.calls in self._fail:
            raise ProviderUnavailableError(f"boom {self.calls}")
        path = self._storage.save(self._content)
        return ImageGenerationResponse(
            image_path=path, provider="fake", model="fake", generation_time=0.0
        )


class _FailingPollinationsClient:
    """A Pollinations client that fails transiently N times before succeeding."""

    def __init__(self, *, fail_times: int, data: bytes) -> None:
        self._fail = fail_times
        self._data = data
        self.calls = 0

    async def generate(self, request: ImageGenerationRequest, *, model: str) -> bytes:
        self.calls += 1
        if self._fail > 0:
            self._fail -= 1
            raise ProviderUnavailableError("503")
        return self._data

    async def list_models(self) -> list[str]:
        return ["flux"]


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


def _use_fake_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **kwargs: object
) -> _FakeImageProvider:
    fake = _FakeImageProvider(ImageStorage(tmp_path / "fakework"), **kwargs)  # type: ignore[arg-type]
    monkeypatch.setattr(ic.ImageProviderFactory, "create", lambda *a, **k: fake)
    return fake


def test_image_command_generates_saves_and_writes_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_fake_provider(monkeypatch, tmp_path)
    prompts_path = tmp_path / "image_prompts.json"
    prompts_path.write_text(_image_prompts_json(3), encoding="utf-8")

    result = runner.invoke(app, ["image", "--input", str(prompts_path)])

    assert result.exit_code == 0
    images_dir = tmp_path / "out" / "images"
    assert (images_dir / "001.png").exists()
    assert (images_dir / "002.png").exists()
    assert (images_dir / "003.png").exists()
    assert not (images_dir / ".work").exists()  # work dir cleaned up

    manifest = json.loads((images_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["count"] == 3
    first = manifest["images"][0]
    assert first["index"] == 1
    assert first["filename"] == "001.png"
    assert first["prompt"] == "visual 1"
    assert first["provider"] == "pollinations"  # config default
    assert first["model"] == "flux"
    assert first["width"] == 64
    assert first["height"] == 96
    assert "created_at" in first


def test_image_command_missing_input_fails(tmp_path: Path) -> None:
    result = runner.invoke(app, ["image", "--input", str(tmp_path / "nope.json")])
    assert result.exit_code == 1


def test_image_command_skips_existing_per_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = _use_fake_provider(monkeypatch, tmp_path)
    images_dir = tmp_path / "out" / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "001.png").write_bytes(_png_bytes(10, 10))  # pre-existing -> skipped
    prompts_path = tmp_path / "image_prompts.json"
    prompts_path.write_text(_image_prompts_json(3), encoding="utf-8")

    result = runner.invoke(app, ["image", "--input", str(prompts_path)])

    assert result.exit_code == 0
    assert (images_dir / "001.png").read_bytes() == _png_bytes(10, 10)  # untouched
    assert (images_dir / "002.png").exists()
    assert (images_dir / "003.png").exists()
    assert fake.calls == 2  # only the two missing images were generated
    manifest = json.loads((images_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["count"] == 3  # skipped file is still listed


def test_image_command_skips_all_when_present(tmp_path: Path) -> None:
    # All files exist -> everything skipped, no provider call, no network needed.
    images_dir = tmp_path / "out" / "images"
    images_dir.mkdir(parents=True)
    for i in (1, 2):
        (images_dir / f"{i:03d}.png").write_bytes(_png_bytes(8, 8))
    prompts_path = tmp_path / "image_prompts.json"
    prompts_path.write_text(_image_prompts_json(2), encoding="utf-8")

    result = runner.invoke(app, ["image", "--input", str(prompts_path)])

    assert result.exit_code == 0
    assert "Skipped" in result.stdout


def test_image_command_force_regenerates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_fake_provider(monkeypatch, tmp_path, content=_png_bytes(32, 48))
    images_dir = tmp_path / "out" / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "001.png").write_bytes(b"OLD")
    prompts_path = tmp_path / "image_prompts.json"
    prompts_path.write_text(_image_prompts_json(1), encoding="utf-8")

    result = runner.invoke(app, ["image", "--input", str(prompts_path), "--force"])

    assert result.exit_code == 0
    assert (images_dir / "001.png").read_bytes() == _png_bytes(32, 48)


def test_image_command_continues_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_fake_provider(monkeypatch, tmp_path, fail_calls={2})  # second prompt fails
    prompts_path = tmp_path / "image_prompts.json"
    prompts_path.write_text(_image_prompts_json(3), encoding="utf-8")

    result = runner.invoke(app, ["image", "--input", str(prompts_path)])

    assert result.exit_code == 0
    images_dir = tmp_path / "out" / "images"
    assert (images_dir / "001.png").exists()
    assert not (images_dir / "002.png").exists()  # failed
    assert (images_dir / "003.png").exists()
    assert "2 generated, 0 skipped, 1 failed" in result.stdout
    manifest = json.loads((images_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["count"] == 2  # only the two successes


def test_image_command_retries_transient_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def _no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)  # patch before building the limiter
    client = _FailingPollinationsClient(fail_times=2, data=_png_bytes(16, 16))
    provider = PollinationsImageProvider(
        ImageProviderSettings(provider="pollinations", retry_count=3),
        ImageStorage(tmp_path / "work"),
        client=client,
    )
    monkeypatch.setattr(ic.ImageProviderFactory, "create", lambda *a, **k: provider)
    prompts_path = tmp_path / "image_prompts.json"
    prompts_path.write_text(_image_prompts_json(1), encoding="utf-8")

    result = runner.invoke(app, ["image", "--input", str(prompts_path)])

    assert result.exit_code == 0
    assert client.calls == 3  # two transient failures + one success
    assert (tmp_path / "out" / "images" / "001.png").exists()
    assert "1 generated, 0 skipped, 0 failed" in result.stdout
