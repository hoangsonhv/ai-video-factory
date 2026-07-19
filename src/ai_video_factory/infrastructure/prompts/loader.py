"""Prompt loader — reads prompt templates from the prompt root and caches them.

A prompt ``name`` is a ``/``-separated path without the ``.md`` extension, e.g.
``story/idea`` maps to ``<root>/story/idea.md``.
"""

from __future__ import annotations

from pathlib import Path

from ai_video_factory.infrastructure.prompts.errors import PromptNotFoundError


class PromptLoader:
    """Loads prompt template text from disk with an in-memory cache."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._cache: dict[str, str] = {}

    def load(self, name: str) -> str:
        """Return the raw template text for ``name``.

        Raises:
            PromptNotFoundError: If no template file exists for ``name``.
        """
        if name in self._cache:
            return self._cache[name]
        path = self._path_for(name)
        if not path.is_file():
            raise PromptNotFoundError(f"prompt {name!r} not found", context={"path": str(path)})
        text = path.read_text(encoding="utf-8")
        self._cache[name] = text
        return text

    def list_names(self) -> list[str]:
        """Return every available prompt name (sorted, ``/``-separated)."""
        if not self._root.is_dir():
            return []
        names = [
            path.relative_to(self._root).with_suffix("").as_posix()
            for path in self._root.rglob("*.md")
        ]
        return sorted(names)

    def _path_for(self, name: str) -> Path:
        clean = name.strip().removesuffix(".md")
        parts = clean.split("/")
        if not clean or clean.startswith("/") or ".." in parts or "" in parts:
            raise PromptNotFoundError(f"invalid prompt name {name!r}")
        return self._root.joinpath(*parts).with_suffix(".md")
