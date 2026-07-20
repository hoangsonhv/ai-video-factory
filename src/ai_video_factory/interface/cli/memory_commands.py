"""``ai-video-factory character memory`` CLI command (interface layer).

Thin command: read the storyboard, the continuity prompts and the character
bible, derive or reload the character memory, adopt reference images, rewrite
every prompt to restate the remembered identity, and save the results.

Deterministic and offline — no provider is contacted, no image is generated,
and no video or compose stage is touched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ai_video_factory.errors import AppError
from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.infrastructure.memory.builder import (
    adopt_references,
    derive_memory,
    merge_memory,
)
from ai_video_factory.infrastructure.memory.engine import CharacterMemoryEngine
from ai_video_factory.infrastructure.memory.enricher import supports_image_reference
from ai_video_factory.infrastructure.memory.reader import (
    read_character_bible,
    read_movie,
    read_optional_memory,
    read_prompts,
    read_storyboard,
    scan_images,
    write_appearance_scores,
    write_memory,
    write_prompts,
)
from ai_video_factory.infrastructure.memory.validator import PASS_THRESHOLD
from ai_video_factory.interface.presenters.memory_presenter import (
    render_appearance_scores,
    render_memory,
)
from ai_video_factory.shared.console import ensure_utf8_stdout

_console = Console()

MEMORY_FILE = "character_memory.json"
SCORES_FILE = "appearance_scores.json"
PROMPTS_FILE = "shot_image_prompts.json"
BIBLE_FILE = "character_bible.json"
MOVIE_FILE = "movie_consistent.json"
IMAGES_DIR = "images"


def character_memory_command(
    storyboard_path: Annotated[
        Path, typer.Option("--storyboard", help="Path to a storyboard JSON file.")
    ] = Path("output/storyboard.json"),
    prompts_path: Annotated[
        Path | None,
        typer.Option("--prompts", help="Continuity prompts to enrich."),
    ] = None,
    images: Annotated[
        Path | None,
        typer.Option("--images", help="Directory of generated images to adopt references from."),
    ] = None,
    threshold: Annotated[
        int,
        typer.Option("--threshold", help="Minimum appearance score.", min=0, max=100),
    ] = PASS_THRESHOLD,
) -> None:
    """Pin every character's look so each image matches the first one made.

    An existing ``character_memory.json`` is reloaded and its canonical values
    are never overwritten — that is what keeps a character stable across runs.
    """
    ensure_utf8_stdout()
    settings = load_settings()
    output_dir = settings.app.output_dir
    prompts_source = prompts_path or output_dir / PROMPTS_FILE
    images_dir = images if images is not None else output_dir / IMAGES_DIR
    provider = settings.image_provider.provider

    try:
        storyboard = read_storyboard(storyboard_path)
        prompts = read_prompts(prompts_source)
        bible = read_character_bible(output_dir / BIBLE_FILE)
        movie = read_movie(output_dir / MOVIE_FILE)

        derived = derive_memory(bible, movie, style=movie.style)
        remembered = read_optional_memory(output_dir / MEMORY_FILE)
        memory = merge_memory(remembered, derived) if remembered else derived
        memory = adopt_references(memory, storyboard, scan_images(images_dir))

        engine = CharacterMemoryEngine(threshold=threshold, provider=provider)
        result = engine.run(storyboard, prompts, memory)
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    write_memory(output_dir / MEMORY_FILE, result.memory)
    write_prompts(prompts_source, result.prompts)
    write_appearance_scores(output_dir / SCORES_FILE, result.scores)

    render_memory(result.memory, output_dir / MEMORY_FILE)
    render_appearance_scores(result.scores, output_dir / SCORES_FILE)

    without = [c.character_id for c in result.memory.characters if not c.has_reference]
    if without:
        _console.print(
            f"[yellow]Note:[/yellow] no reference image yet for {', '.join(without)} — "
            f"none was found in {images_dir}. The first image generated for each will be "
            "adopted on the next run."
        )
    if not supports_image_reference(provider):
        _console.print(
            f"[yellow]Note:[/yellow] the {provider!r} image driver takes no reference image, "
            "so the reference is described in the prompt instead."
        )
    failing = result.scores.failing
    if failing:
        unremembered = sorted(
            {
                issue
                for score in failing
                for issue in score.issues
                if issue.endswith("(not remembered)")
            }
        )
        detail = f" — the memory has no {', '.join(unremembered)}" if unremembered else ""
        _console.print(
            f"[yellow]Note:[/yellow] {len(failing)} prompt(s) stayed below {threshold} after "
            f"rebuilding{detail}. Fill the gap in {BIBLE_FILE} or {MEMORY_FILE} to raise it."
        )
    drifted = [c.character_id for c in result.memory.characters if c.is_drifted]
    if drifted:
        _console.print(
            f"[red]Warning:[/red] the remembered appearance of {', '.join(drifted)} no longer "
            "matches its hash — images already generated for them are stale."
        )
    _console.print(
        f"[green]Saved[/green] memory for {len(result.memory.characters)} character(s), "
        f"average appearance score {result.scores.average}, to {output_dir / MEMORY_FILE}"
    )
