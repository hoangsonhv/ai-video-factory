"""``ai-video-factory chapter`` CLI command (interface layer).

Thin command: read the outline, run the chapter generator, present the chapter,
and save it. All generation logic lives in the infrastructure service.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ai_video_factory.errors import AppError
from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.infrastructure.story.chapter_generator import ChapterGenerator
from ai_video_factory.infrastructure.story.reader import read_outline
from ai_video_factory.infrastructure.story.writer import write_chapter_json
from ai_video_factory.interface.presenters.chapter_presenter import render_chapter

_console = Console()


def chapter_command(
    outline: Annotated[Path, typer.Option("--outline", help="Path to a story outline JSON file.")],
    language: Annotated[str, typer.Option("--language", help="Output language.")] = "vi",
) -> None:
    """Generate the full chapter prose from an outline with the configured provider."""
    settings = load_settings()
    try:
        story_outline = read_outline(outline)
        generator = ChapterGenerator.from_settings(settings)
        chapter = asyncio.run(generator.generate(story_outline, language=language))
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    render_chapter(chapter)
    output_path = settings.app.output_dir / "chapter.json"
    write_chapter_json(output_path, chapter)
    _console.print(
        f"[green]Saved[/green] chapter (~{chapter.estimated_duration_seconds}s) to {output_path}"
    )
