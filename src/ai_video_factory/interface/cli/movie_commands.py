"""``ai-video-factory movie`` CLI command (interface layer).

Thin command: read the chapter, run the Movie Builder, present the movie, and
save it to ``output/movie.json``. All logic lives in the infrastructure Movie
Builder. This adds a new stage and does not alter the existing pipeline.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ai_video_factory.errors import AppError
from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.infrastructure.story.movie_builder import (
    DEFAULT_GENRE,
    DEFAULT_STYLE,
    MovieBuilder,
)
from ai_video_factory.infrastructure.story.movie_writer import write_movie_json
from ai_video_factory.infrastructure.story.reader import read_chapter
from ai_video_factory.interface.presenters.movie_presenter import render_movie_summary
from ai_video_factory.shared.console import ensure_utf8_stdout

_console = Console()


def movie_command(
    input_path: Annotated[Path, typer.Option("--input", help="Path to a chapter JSON file.")],
    style: Annotated[str, typer.Option("--style", help="Visual style.")] = DEFAULT_STYLE,
    genre: Annotated[str, typer.Option("--genre", help="Story genre.")] = DEFAULT_GENRE,
    language: Annotated[str, typer.Option("--language", help="Dialogue language.")] = "vi",
) -> None:
    """Build a structured movie bible (characters + scenes) from a chapter."""
    ensure_utf8_stdout()
    settings = load_settings()
    try:
        chapter = read_chapter(input_path)
        builder = MovieBuilder.from_settings(settings)
        movie = asyncio.run(builder.build(chapter, style=style, genre=genre, language=language))
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    output_path = settings.app.output_dir / "movie.json"
    write_movie_json(output_path, movie)
    render_movie_summary(movie, output_path)
    _console.print(
        f"[green]Saved[/green] movie ({len(movie.characters)} characters, "
        f"{len(movie.scenes)} scenes) to {output_path}"
    )
