"""Filesystem storage for generated subtitles (infrastructure/media).

Saves subtitle text to a single UTF-8 file (default ``narration.srt``) under a
directory, so Vietnamese diacritics are preserved.
"""

from __future__ import annotations

from pathlib import Path


class SubtitleStorage:
    """Saves subtitle text to a single UTF-8 file under a directory."""

    def __init__(self, directory: Path, *, filename: str = "narration.srt") -> None:
        self._directory = directory
        self._filename = filename

    @property
    def directory(self) -> Path:
        """The directory subtitles are saved to."""
        return self._directory

    def save(self, text: str) -> Path:
        """Write ``text`` to the subtitle file (UTF-8) and return its path."""
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / self._filename
        path.write_text(text, encoding="utf-8")
        return path
