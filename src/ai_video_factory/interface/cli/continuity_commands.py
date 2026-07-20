"""``ai-video-factory continuity`` CLI command (interface layer).

Thin command: read the storyboard and the bibles (deriving them from the
character library and movie when they do not exist yet), run the Visual
Continuity Engine, present the scores, and save the four artifacts. All logic
lives in the infrastructure engine. Deterministic and offline — no provider is
contacted, and no video stage is touched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ai_video_factory.errors import AppError
from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.infrastructure.continuity.engine import VisualContinuityEngine
from ai_video_factory.infrastructure.continuity.reader import (
    read_character_library,
    read_movie,
    read_optional_character_bible,
    read_optional_world_bible,
    read_storyboard,
    write_character_bible,
    write_prompt_scores,
    write_shot_image_prompts,
    write_visual_context,
    write_world_bible,
)
from ai_video_factory.infrastructure.continuity.scorer import PASS_THRESHOLD
from ai_video_factory.interface.presenters.continuity_presenter import render_scores
from ai_video_factory.shared.console import ensure_utf8_stdout

_console = Console()

CHARACTER_BIBLE = "character_bible.json"
WORLD_BIBLE = "world_bible.json"
VISUAL_CONTEXT = "visual_context.json"
SHOT_PROMPTS = "shot_image_prompts.json"
PROMPT_SCORES = "prompt_scores.json"
LIBRARY = "character_library.json"
MOVIE = "movie_consistent.json"


def continuity_command(
    storyboard_path: Annotated[
        Path, typer.Option("--storyboard", help="Path to a storyboard JSON file.")
    ] = Path("output/storyboard.json"),
    movie_path: Annotated[
        Path | None,
        typer.Option("--movie", help="Movie the world bible is derived from."),
    ] = None,
    library_path: Annotated[
        Path | None,
        typer.Option("--library", help="Character library the character bible is derived from."),
    ] = None,
    threshold: Annotated[
        int,
        typer.Option(
            "--threshold", help="Minimum continuity score a prompt must reach.", min=0, max=100
        ),
    ] = PASS_THRESHOLD,
) -> None:
    """Build continuity-aware image prompts from a storyboard.

    Existing ``character_bible.json`` / ``world_bible.json`` are used as-is, so
    hand edits survive; otherwise both are derived and written out.
    """
    ensure_utf8_stdout()
    settings = load_settings()
    output_dir = settings.app.output_dir
    movie_source = movie_path or output_dir / MOVIE
    library_source = library_path or output_dir / LIBRARY

    try:
        storyboard = read_storyboard(storyboard_path)
        engine = VisualContinuityEngine(threshold=threshold)

        existing_characters = read_optional_character_bible(output_dir / CHARACTER_BIBLE)
        existing_world = read_optional_world_bible(output_dir / WORLD_BIBLE)
        derived = existing_characters is None or existing_world is None
        if existing_characters is None or existing_world is None:
            # Only what is missing is derived; a hand-edited bible is kept.
            library = read_character_library(library_source)
            movie = read_movie(movie_source)
            fresh_characters, fresh_world = engine.derive_bibles(library, movie)
            character_bible = existing_characters or fresh_characters
            world_bible = existing_world or fresh_world
        else:
            character_bible = existing_characters
            world_bible = existing_world

        result = engine.run(storyboard, character_bible, world_bible)
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    write_character_bible(output_dir / CHARACTER_BIBLE, result.character_bible)
    write_world_bible(output_dir / WORLD_BIBLE, result.world_bible)
    write_visual_context(output_dir / VISUAL_CONTEXT, result.context)
    write_shot_image_prompts(output_dir / SHOT_PROMPTS, result.prompts)
    write_prompt_scores(output_dir / PROMPT_SCORES, result.scores)

    render_scores(result.scores, output_dir / PROMPT_SCORES)

    if derived:
        _console.print(
            f"[yellow]Note:[/yellow] derived the bibles from {library_source.name} and "
            f"{movie_source.name}. Edit {CHARACTER_BIBLE} / {WORLD_BIBLE} to enrich them; "
            "later runs keep your edits."
        )
    failing = result.scores.failing
    if failing:
        _console.print(
            f"[yellow]Note:[/yellow] {len(failing)} prompt(s) stayed below {threshold} after "
            "recomposing. The missing elements are absent from the storyboard, not the prompt "
            "— see prompt_scores.json."
        )
    _console.print(
        f"[green]Saved[/green] {len(result.prompts)} continuity prompt(s), "
        f"average score {result.scores.average}, to {output_dir / SHOT_PROMPTS}"
    )
