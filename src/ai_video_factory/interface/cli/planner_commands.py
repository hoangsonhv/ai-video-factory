"""``ai-video-factory shot-plan`` CLI command (interface layer).

Thin command: read the storyboard, the directed movie and the bibles, plan how
every frame is composed, rebuild the image prompts from that plan, and save the
plan, the prompts and the statistics. All logic lives in the infrastructure
planning engine.

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
from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.infrastructure.planner.engine import ShotPlanningEngine
from ai_video_factory.infrastructure.planner.reader import (
    read_character_bible,
    read_directed_movie,
    read_storyboard,
    read_world_bible,
    write_plan,
    write_prompts,
    write_statistics,
)
from ai_video_factory.interface.presenters.planner_presenter import (
    render_distribution,
    render_shot_plan,
    render_statistics,
)

_console = Console()

PLAN_FILE = "shot_plan.json"
STATISTICS_FILE = "shot_statistics.json"
PROMPTS_FILE = "shot_image_prompts.json"
CHARACTER_BIBLE = "character_bible.json"
WORLD_BIBLE = "world_bible.json"
DIRECTED_MOVIE = "movie_directed.json"


def _ensure_utf8_stdout() -> None:
    """Switch stdout to UTF-8 so Vietnamese text renders on legacy (cp1252)
    Windows consoles instead of crashing."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    with contextlib.suppress(ValueError, OSError):  # stream may not be reconfigurable
        reconfigure(encoding="utf-8", errors="backslashreplace")


def shot_plan_command(
    storyboard_path: Annotated[
        Path, typer.Option("--storyboard", help="Path to a storyboard JSON file.")
    ] = Path("output/storyboard.json"),
    movie_path: Annotated[
        Path | None,
        typer.Option("--movie", help="Path to the directed movie (supplies dialogue/locations)."),
    ] = None,
    prompts_path: Annotated[
        Path | None,
        typer.Option("--prompts", help="Where to write the planned image prompts."),
    ] = None,
) -> None:
    """Plan how every frame is composed, so the film is not thirty portraits.

    Sizes follow what each scene is doing, the coverage is validated across the
    whole film and re-planned until it balances, and every frame must state
    something in its foreground, midground or background.
    """
    _ensure_utf8_stdout()
    settings = load_settings()
    output_dir = settings.app.output_dir
    prompts_target = prompts_path or output_dir / PROMPTS_FILE

    try:
        storyboard = read_storyboard(storyboard_path)
        bible = read_character_bible(output_dir / CHARACTER_BIBLE)
        world = read_world_bible(output_dir / WORLD_BIBLE)
        movie = read_directed_movie(movie_path or output_dir / DIRECTED_MOVIE)
        result = ShotPlanningEngine().run(storyboard, bible, world, movie)
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    write_plan(output_dir / PLAN_FILE, result.plan)
    write_statistics(output_dir / STATISTICS_FILE, result.statistics)
    write_prompts(prompts_target, result.prompts)

    render_shot_plan(result.plan, output_dir / PLAN_FILE)
    render_statistics(result.statistics)
    render_distribution(result.plan)

    if movie is None:
        _console.print(
            "[yellow]Note:[/yellow] no directed movie found, so no scene could be "
            "recognised as a conversation. Pass --movie to improve the plan."
        )
    if result.sanitized:
        _console.print(
            f"[yellow]Overruled[/yellow] close-up framing written into "
            f"{len(result.sanitized)} shot(s) by an earlier stage: "
            f"{', '.join(str(shot) for shot in result.sanitized)}"
        )
    if not result.plan.distribution.valid:
        _console.print(
            "[red]Coverage still outside its bounds after "
            f"{result.plan.replans} re-plan(s):[/red] " + "; ".join(result.plan.distribution.issues)
        )

    _console.print(
        f"[green]Planned[/green] {len(result.plan.shots)} shot(s); plan written to "
        f"{output_dir / PLAN_FILE}, statistics to {output_dir / STATISTICS_FILE}, "
        f"prompts to {prompts_target}"
    )
    _console.print(
        "[yellow]Note:[/yellow] these prompts replace whatever was at "
        f"{prompts_target.name}. Re-run `character memory` to fold the remembered "
        "identity back in."
    )
