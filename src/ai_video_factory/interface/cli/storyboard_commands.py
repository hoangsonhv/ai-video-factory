"""``ai-video-factory storyboard`` CLI command (interface layer).

Thin command: read the directed movie (plus the narration and character
library when present), lay the shots on a timeline, present it, and save
``output/storyboard.json``. All logic lives in the infrastructure storyboard
builder. Deterministic and offline — no provider is contacted.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ai_video_factory.errors import AppError
from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.infrastructure.storyboard.builder import build_storyboard
from ai_video_factory.infrastructure.storyboard.narration import (
    NarrationCue,
    narration_span,
    read_audio_duration,
    read_narration,
)
from ai_video_factory.infrastructure.storyboard.reader import (
    read_directed_movie,
    read_optional_library,
    write_storyboard_json,
)
from ai_video_factory.interface.presenters.storyboard_presenter import render_storyboard

_console = Console()

STORYBOARD_FILENAME = "storyboard.json"
LIBRARY_FILENAME = "character_library.json"
NARRATION_SUBTITLES = Path("subtitles") / "narration.srt"
NARRATION_AUDIO = Path("audio") / "narration.mp3"
NARRATION_METADATA = Path("audio") / "metadata.json"


def _ensure_utf8_stdout() -> None:
    """Switch stdout to UTF-8 so Vietnamese text renders on legacy (cp1252)
    Windows consoles instead of crashing."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    with contextlib.suppress(ValueError, OSError):  # stream may not be reconfigurable
        reconfigure(encoding="utf-8", errors="backslashreplace")


MISTIMING_TOLERANCE = 0.1
"""Flag the subtitles when their span differs from the audio by over 10%."""


def _warn_if_subtitles_mistimed(
    cues: list[NarrationCue], audio_duration: float, subtitle_path: Path
) -> None:
    """Warn when the subtitle timings disagree with the actual audio length.

    The transcription stage derives cue times from ASR, which can drift badly.
    If the ``.srt`` claims to run far longer (or shorter) than the narration
    really does, every subtitle mapped onto a shot is misplaced — worth saying
    plainly rather than emitting a confidently wrong storyboard.
    """
    span = narration_span(cues)
    if not span or not audio_duration:
        return
    if abs(span - audio_duration) <= audio_duration * MISTIMING_TOLERANCE:
        return
    _console.print(
        f"[yellow]Warning:[/yellow] {subtitle_path} is timed to {span:.1f}s but the "
        f"narration is {audio_duration:.1f}s. The subtitles are mistimed, so the text "
        "mapped onto each shot will be off. Re-run `subtitle` to retime them."
    )


def storyboard_command(
    movie_path: Annotated[
        Path, typer.Option("--movie", help="Path to a directed movie JSON file.")
    ] = Path("output/movie_directed.json"),
    subtitles: Annotated[
        Path | None,
        typer.Option("--subtitles", help="Narration .srt used to map speech onto shots."),
    ] = None,
    library_path: Annotated[
        Path | None,
        typer.Option("--library", help="Path to a character library JSON file."),
    ] = None,
) -> None:
    """Turn a directed movie into a shot-by-shot storyboard."""
    _ensure_utf8_stdout()
    settings = load_settings()
    output_dir = settings.app.output_dir
    subtitle_path = subtitles or output_dir / NARRATION_SUBTITLES
    library_source = library_path or output_dir / LIBRARY_FILENAME

    try:
        movie = read_directed_movie(movie_path)
        cues = read_narration(subtitle_path)
        library = read_optional_library(library_source)
        storyboard = build_storyboard(
            movie,
            cues=cues,
            profiles=(
                {profile.id.strip().lower(): profile for profile in library.characters}
                if library
                else {}
            ),
            audio_source=str(output_dir / NARRATION_AUDIO),
            audio_duration=read_audio_duration(output_dir / NARRATION_METADATA),
        )
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    output_path = output_dir / STORYBOARD_FILENAME
    write_storyboard_json(output_path, storyboard)
    render_storyboard(storyboard, output_path)

    if not cues:
        _console.print(
            f"[yellow]Note:[/yellow] no narration at {subtitle_path} — "
            "shots carry no subtitles. Run `subtitle` first to synchronise speech."
        )
    _warn_if_subtitles_mistimed(cues, storyboard.narration_duration, subtitle_path)
    if storyboard.drift:
        direction = "longer than" if storyboard.drift > 0 else "shorter than"
        _console.print(
            f"[yellow]Note:[/yellow] the shot timeline is {abs(storyboard.drift):.1f}s "
            f"{direction} the narration ({storyboard.narration_duration:.1f}s)."
        )
    _console.print(
        f"[green]Saved[/green] storyboard ({storyboard.shot_count} shots, "
        f"{storyboard.total_duration:.1f}s) to {output_path}"
    )
