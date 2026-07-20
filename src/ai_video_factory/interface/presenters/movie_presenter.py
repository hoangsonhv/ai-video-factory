"""Terminal presenter for the built movie bible (interface layer)."""

from __future__ import annotations

from pathlib import Path

from rich.table import Table

from ai_video_factory.domain.value_objects.movie import Movie
from ai_video_factory.interface.presenters.console_io import emit_renderable


def render_movie_summary(movie: Movie, path: Path) -> None:
    """Render a summary of the built movie."""
    table = Table(title="Movie Bible", show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value", overflow="fold")
    table.add_row("File", str(path))
    table.add_row("Title", movie.title)
    table.add_row("Genre", movie.genre)
    table.add_row("Style", movie.style)
    table.add_row("Duration", f"{movie.duration}s")
    table.add_row("Characters", str(len(movie.characters)))
    table.add_row("Locations", str(len(movie.locations)))
    table.add_row("Scenes", str(len(movie.scenes)))
    emit_renderable(table)
