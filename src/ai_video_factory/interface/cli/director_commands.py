"""``ai-video-factory director`` CLI command (interface layer).

Thin command: read the movie (and the character library, if present), run the
AI Director scene by scene, present the shot list and the outcome, and save the
directed movie. All logic lives in the infrastructure director service. This
adds a new stage and alters no existing one.

The movie is planned **one scene per request**, and the partial result is
written to ``movie_directed.partial.json`` after *every* scene — so an
interrupted run leaves the scenes already planned on disk. A scene that fails
is left unplanned and the run continues; ``--resume`` re-asks only for those.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from pathlib import Path
from typing import Annotated, ClassVar

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TaskID, TextColumn

from ai_video_factory.errors import AppError
from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.infrastructure.director.reader import (
    read_movie,
    read_optional_directed_movie,
    read_optional_library,
    write_directed_movie_json,
)
from ai_video_factory.infrastructure.director.service import DirectorService
from ai_video_factory.interface.presenters.director_presenter import (
    render_direction_report,
    render_shot_list,
)

_console = Console()

DIRECTED_FILENAME = "movie_directed.json"
PARTIAL_FILENAME = "movie_directed.partial.json"
LIBRARY_FILENAME = "character_library.json"


def _ensure_utf8_stdout() -> None:
    """Switch stdout to UTF-8 so Vietnamese text and Rich progress glyphs render
    on legacy (cp1252) Windows consoles instead of crashing."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    with contextlib.suppress(ValueError, OSError):  # stream may not be reconfigurable
        reconfigure(encoding="utf-8", errors="backslashreplace")


class _PlanProgress:
    """Narrates the run scene by scene, including retries and failures."""

    _LABELS: ClassVar[dict[str, str]] = {
        "planning": "Planning scene by scene ({scenes} left)",
        "retrying": "[yellow]Retrying scene {scenes}",
        "failed": "[red]Scene failed; continuing ({scenes} left)",
        "mapping": "Merging the planned scenes",
        "done": "Directed",
    }

    def __init__(self, progress: Progress, task: TaskID, total: int) -> None:
        self._progress = progress
        self._task = task
        self._total = total

    def __call__(self, scenes: int, phase: str) -> None:
        label = self._LABELS.get(phase, phase).format(scenes=scenes)
        completed = self._total if phase == "done" else max(0, self._total - scenes)
        self._progress.update(self._task, description=label, completed=completed)


def director_command(
    movie_path: Annotated[Path, typer.Option("--movie", help="Path to a movie JSON file.")] = Path(
        "output/movie_consistent.json"
    ),
    library_path: Annotated[
        Path | None,
        typer.Option("--library", help="Path to a character library JSON file."),
    ] = None,
    resume: Annotated[
        bool,
        typer.Option("--resume", help="Keep already-directed scenes; retry only the failed ones."),
    ] = False,
) -> None:
    """Plan every shot of a movie and write the directed movie."""
    _ensure_utf8_stdout()
    settings = load_settings()
    output_dir = settings.app.output_dir
    library_source = library_path or output_dir / LIBRARY_FILENAME
    partial_path = output_dir / PARTIAL_FILENAME
    directed_path = output_dir / DIRECTED_FILENAME

    try:
        movie = read_movie(movie_path)
        library = read_optional_library(library_source)
        previous = read_optional_directed_movie(partial_path, directed_path) if resume else None
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if resume and previous is None:
        _console.print(
            f"[yellow]Note:[/yellow] nothing to resume from ({partial_path}) — "
            "directing every scene."
        )

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=_console,
        ) as progress:
            total = len(movie.scenes)
            task = progress.add_task("Directing", total=total)
            reporter = _PlanProgress(progress, task, total)
            service = DirectorService.from_settings(
                settings,
                on_progress=reporter,
                # Saved after every scene, so an interrupted run keeps its work.
                on_scene_saved=lambda partial: write_directed_movie_json(partial_path, partial),
            )
            directed, report = asyncio.run(service.direct(movie, library, resume_from=previous))
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    output_path = directed_path if report.is_complete else partial_path
    if report.directed or report.skipped:
        write_directed_movie_json(output_path, directed)
        if report.is_complete:
            partial_path.unlink(missing_ok=True)  # the run is whole again

    render_shot_list(directed, output_path)
    render_direction_report(report, output_path)

    if library is None:
        _console.print(
            f"[yellow]Note:[/yellow] no character library at {library_source} — "
            "directed prompts carry camera and motion language only."
        )
    if report.is_complete:
        _console.print(f"[green]Saved[/green] directed movie to {output_path}")
        return

    if report.directed or report.skipped:
        _console.print(
            f"[yellow]Saved partial[/yellow] directed movie to {output_path}. "
            "Re-run with --resume to finish the failed scenes."
        )
    else:
        _console.print("[red]No scene could be directed.[/red] Nothing was saved.")
    raise typer.Exit(code=1)
