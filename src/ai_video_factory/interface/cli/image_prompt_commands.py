"""``ai-video-factory image-prompt`` CLI command (interface layer).

Thin command: read the chapter, run the image-prompt generator, present the
prompts, and save them. All generation logic lives in the infrastructure
service. This produces prompt text only — no images are generated.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ai_video_factory.errors import AppError
from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.infrastructure.story.image_prompt_generator import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_COUNT,
    DEFAULT_STYLE,
    ImagePromptGenerator,
)
from ai_video_factory.infrastructure.story.reader import read_chapter
from ai_video_factory.infrastructure.story.writer import write_image_prompts_json
from ai_video_factory.interface.presenters.image_prompt_presenter import render_image_prompts

_console = Console()


def image_prompt_command(
    chapter: Annotated[Path, typer.Option("--chapter", help="Path to a chapter JSON file.")],
    style: Annotated[str, typer.Option("--style", help="Visual style.")] = DEFAULT_STYLE,
    aspect_ratio: Annotated[
        str, typer.Option("--aspect-ratio", help="Aspect ratio, e.g. 9:16.")
    ] = DEFAULT_ASPECT_RATIO,
    count: Annotated[
        int, typer.Option("--count", help="Number of visuals to request.")
    ] = DEFAULT_COUNT,
    language: Annotated[
        str, typer.Option("--language", help="Language for narration context.")
    ] = "vi",
) -> None:
    """Generate cinematic image prompts from a chapter with the configured provider."""
    settings = load_settings()
    try:
        story_chapter = read_chapter(chapter)
        generator = ImagePromptGenerator.from_settings(settings)
        prompts = asyncio.run(
            generator.generate(
                story_chapter,
                style=style,
                aspect_ratio=aspect_ratio,
                count=count,
                language=language,
            )
        )
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    render_image_prompts(prompts)
    output_path = settings.app.output_dir / "image_prompts.json"
    write_image_prompts_json(output_path, prompts)
    _console.print(f"[green]Saved[/green] {len(prompts)} image prompts to {output_path}")
