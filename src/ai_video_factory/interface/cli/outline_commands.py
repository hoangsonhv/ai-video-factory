"""``ai-video-factory outline`` CLI command (interface layer).

Thin command: read a selected idea, run the outline generator, present the
outline, and save it. All generation logic lives in the infrastructure service.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ai_video_factory.errors import AppError
from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.infrastructure.story.outline_generator import OutlineGenerator
from ai_video_factory.infrastructure.story.reader import read_idea
from ai_video_factory.infrastructure.story.writer import write_outline_json
from ai_video_factory.interface.presenters.outline_presenter import render_outline

_console = Console()


def outline_command(
    idea: Annotated[Path, typer.Option("--idea", help="Path to an ideas JSON file.")],
    index: Annotated[int, typer.Option("--index", help="Which idea to expand (0-based).")] = 0,
    chapters: Annotated[int, typer.Option("--chapters", help="Number of chapters.")] = 10,
    duration: Annotated[str, typer.Option("--duration", help="Target duration, e.g. 60s.")] = "60s",
    language: Annotated[str, typer.Option("--language", help="Output language.")] = "vi",
) -> None:
    """Generate a story outline from a selected idea with the configured provider."""
    settings = load_settings()
    try:
        story_idea = read_idea(idea, index)
        generator = OutlineGenerator.from_settings(settings)
        outline = asyncio.run(
            generator.generate(
                story_idea,
                target_duration=duration,
                chapter_count=chapters,
                language=language,
            )
        )
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    render_outline(outline)
    output_path = settings.app.output_dir / "story_outline.json"
    write_outline_json(output_path, outline)
    _console.print(
        f"[green]Saved[/green] outline ({len(outline.chapter_outlines)} chapters) to {output_path}"
    )
