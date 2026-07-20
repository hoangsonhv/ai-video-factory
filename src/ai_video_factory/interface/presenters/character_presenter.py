"""Terminal presenters for the character consistency stage (interface layer)."""

from __future__ import annotations

from pathlib import Path

from rich.table import Table

from ai_video_factory.domain.value_objects.character_library import CharacterLibrary
from ai_video_factory.domain.value_objects.movie import Movie
from ai_video_factory.interface.presenters.console_io import emit_renderable


def render_character_library(library: CharacterLibrary, path: Path) -> None:
    """Render one row per character profile."""
    table = Table(title=f"Character Library — {path}")
    table.add_column("ID", style="bold")
    table.add_column("Seed", justify="right")
    table.add_column("Master prompt", overflow="fold")
    for profile in library.characters:
        table.add_row(profile.id, str(profile.seed), profile.master_prompt)
    emit_renderable(table)


def render_injection_summary(movie: Movie, path: Path) -> None:
    """Render a summary of the consistency-corrected movie."""
    table = Table(title="Character Injection", show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value", overflow="fold")
    table.add_row("File", str(path))
    table.add_row("Title", movie.title)
    table.add_row("Scenes injected", str(sum(1 for scene in movie.scenes if scene.characters)))
    table.add_row("Scenes total", str(len(movie.scenes)))
    emit_renderable(table)
