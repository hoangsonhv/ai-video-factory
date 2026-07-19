"""Tests for the image filesystem storage."""

from __future__ import annotations

from pathlib import Path

from ai_video_factory.infrastructure.media.image_storage import ImageStorage


def test_save_numbers_files_sequentially(tmp_path: Path) -> None:
    storage = ImageStorage(tmp_path / "images")
    first = storage.save(b"one")
    second = storage.save(b"two")
    assert first.name == "image_001.png"
    assert second.name == "image_002.png"


def test_save_writes_bytes_and_creates_dir(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "images"
    storage = ImageStorage(target)
    path = storage.save(b"PNGDATA")
    assert path.exists()
    assert path.read_bytes() == b"PNGDATA"
    assert storage.directory == target


def test_custom_prefix(tmp_path: Path) -> None:
    storage = ImageStorage(tmp_path, prefix="scene")
    assert storage.save(b"x").name == "scene_001.png"


def test_empty_prefix_numbers_only(tmp_path: Path) -> None:
    storage = ImageStorage(tmp_path, prefix="")
    assert storage.save(b"one").name == "001.png"
    assert storage.save(b"two").name == "002.png"
