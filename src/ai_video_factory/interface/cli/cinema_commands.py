"""``ai-video-factory cinema`` CLI command (interface layer).

Thin command: read the storyboard and the bibles, run the Scene and Shot
Directors, rebuild every image prompt from their decisions, and save both.
All logic lives in the infrastructure cinematic director.

Deterministic and offline — no provider is contacted, and no video or compose
stage is touched.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ai_video_factory.errors import AppError
from ai_video_factory.infrastructure.cinema.engine import CinematicDirector
from ai_video_factory.infrastructure.cinema.reader import (
    read_character_bible,
    read_storyboard,
    read_world_bible,
    write_direction,
    write_prompts,
)
from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.interface.presenters.cinema_presenter import (
    render_coverage,
    render_shot_list,
)

_console = Console()

DIRECTION_FILE = "cinematic_direction.json"
PROMPTS_FILE = "shot_image_prompts.json"
CHARACTER_BIBLE = "character_bible.json"
WORLD_BIBLE = "world_bible.json"


def _ensure_utf8_stdout() -> None:
    """Switch stdout to UTF-8 so Vietnamese text renders on legacy (cp1252)
    Windows consoles instead of crashing."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    with contextlib.suppress(ValueError, OSError):  # stream may not be reconfigurable
        reconfigure(encoding="utf-8", errors="backslashreplace")


def cinema_command(
    storyboard_path: Annotated[
        Path, typer.Option("--storyboard", help="Path to a storyboard JSON file.")
    ] = Path("output/storyboard.json"),
    prompts_path: Annotated[
        Path | None,
        typer.Option("--prompts", help="Where to write the directed image prompts."),
    ] = None,
) -> None:
    """Direct the film — scene purpose, then camera, composition and light.

    Rebuilds every image prompt from the director's decisions, so the camera
    and lens come from a choice rather than a default.
    """
    _ensure_utf8_stdout()
    settings = load_settings()
    output_dir = settings.app.output_dir
    prompts_target = prompts_path or output_dir / PROMPTS_FILE

    try:
        storyboard = read_storyboard(storyboard_path)
        bible = read_character_bible(output_dir / CHARACTER_BIBLE)
        world = read_world_bible(output_dir / WORLD_BIBLE)
        result = CinematicDirector().run(storyboard, bible, world)
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    write_direction(output_dir / DIRECTION_FILE, result.direction)
    write_prompts(prompts_target, result.prompts)

    render_shot_list(result.direction, output_dir / DIRECTION_FILE)
    render_coverage(result.direction)

    _console.print(
        f"[green]Directed[/green] {len(result.direction.shots)} shot(s) across "
        f"{len(result.direction.scenes)} scene(s); prompts written to {prompts_target}"
    )
    _console.print(
        "[yellow]Note:[/yellow] these prompts replace the continuity prompts at "
        f"{prompts_target.name}. Re-run `character memory` to fold the remembered "
        "identity back in."
    )
