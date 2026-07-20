"""``ai-video-factory character`` CLI command group (interface layer).

Thin commands: read the movie bible, run the deterministic consistency
services, present the result, and save it. This adds a new stage and alters
neither the Movie Builder nor the image provider.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ai_video_factory.errors import AppError
from ai_video_factory.infrastructure.character.injector import CharacterPromptInjector
from ai_video_factory.infrastructure.character.reader import read_character_library, read_movie
from ai_video_factory.infrastructure.character.service import CharacterConsistencyService
from ai_video_factory.infrastructure.character.writer import (
    write_character_library_json,
    write_consistent_movie_json,
)
from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.interface.cli.memory_commands import character_memory_command
from ai_video_factory.interface.presenters.character_presenter import (
    render_character_library,
    render_injection_summary,
)

character_app = typer.Typer(
    no_args_is_help=True,
    help="Build and apply the character consistency library.",
)
_console = Console()

LIBRARY_FILENAME = "character_library.json"
CONSISTENT_MOVIE_FILENAME = "movie_consistent.json"


def _ensure_utf8_stdout() -> None:
    """Switch stdout to UTF-8 so Vietnamese text renders on legacy (cp1252)
    Windows consoles instead of crashing."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    with contextlib.suppress(ValueError, OSError):  # stream may not be reconfigurable
        reconfigure(encoding="utf-8", errors="backslashreplace")


@character_app.command("build")
def character_build_command(
    input_path: Annotated[Path, typer.Option("--input", help="Path to a movie JSON file.")] = Path(
        "output/movie.json"
    ),
) -> None:
    """Build the character consistency library from a movie bible."""
    _ensure_utf8_stdout()
    settings = load_settings()
    try:
        movie = read_movie(input_path)
        library = CharacterConsistencyService().build(movie)
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    output_path = settings.app.output_dir / LIBRARY_FILENAME
    write_character_library_json(output_path, library)
    render_character_library(library, output_path)
    merged = len(movie.characters) - len(library.characters)
    if merged > 0:
        _console.print(f"[yellow]Merged[/yellow] {merged} duplicate character record(s)")
    _console.print(
        f"[green]Saved[/green] {len(library.characters)} character profile(s) to {output_path}"
    )


@character_app.command("inject")
def character_inject_command(
    movie_path: Annotated[Path, typer.Option("--movie", help="Path to a movie JSON file.")] = Path(
        "output/movie.json"
    ),
    library_path: Annotated[
        Path | None,
        typer.Option("--library", help="Path to a character library JSON file."),
    ] = None,
) -> None:
    """Bind every scene prompt to the character library."""
    _ensure_utf8_stdout()
    settings = load_settings()
    library_source = library_path or settings.app.output_dir / LIBRARY_FILENAME
    try:
        movie = read_movie(movie_path)
        library = read_character_library(library_source)
        injected = CharacterPromptInjector(library).inject(movie)
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    output_path = settings.app.output_dir / CONSISTENT_MOVIE_FILENAME
    write_consistent_movie_json(output_path, injected)
    render_injection_summary(injected, output_path)
    _console.print(f"[green]Saved[/green] consistent movie to {output_path}")


character_app.command("memory")(character_memory_command)
