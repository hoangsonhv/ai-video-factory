"""Filesystem storage for generated audio (infrastructure/media).

Saves audio bytes to a single named file (default ``narration.mp3``) under a
directory.
"""

from __future__ import annotations

from pathlib import Path


class AudioStorage:
    """Saves audio bytes to a single file under a directory."""

    def __init__(self, directory: Path, *, filename: str = "narration.mp3") -> None:
        self._directory = directory
        self._filename = filename

    @property
    def directory(self) -> Path:
        """The directory audio is saved to."""
        return self._directory

    def save(self, data: bytes) -> Path:
        """Write ``data`` to the audio file and return its path."""
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / self._filename
        path.write_bytes(data)
        return path
