"""Filesystem storage for generated images (infrastructure/media).

Saves image bytes to sequentially numbered PNG files (``image_001.png``,
``image_002.png``, ...) under a directory. One instance numbers a single run.
"""

from __future__ import annotations

from pathlib import Path


class ImageStorage:
    """Saves image bytes to sequentially numbered PNG files."""

    def __init__(self, directory: Path, *, prefix: str = "image") -> None:
        self._directory = directory
        self._prefix = prefix
        self._counter = 0

    @property
    def directory(self) -> Path:
        """The directory images are saved to."""
        return self._directory

    def save(self, data: bytes) -> Path:
        """Write ``data`` to the next numbered PNG file and return its path.

        With a prefix the file is ``<prefix>_001.png``; with an empty prefix it
        is just ``001.png``.
        """
        self._counter += 1
        self._directory.mkdir(parents=True, exist_ok=True)
        stem = f"{self._prefix}_{self._counter:03d}" if self._prefix else f"{self._counter:03d}"
        path = self._directory / f"{stem}.png"
        path.write_bytes(data)
        return path
