"""``ai-video-factory idea`` CLI command (interface layer).

Thin command: build the brief, run the idea generator, present the table, and
save the result. All generation logic lives in the infrastructure service.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.console import Console

from ai_video_factory.domain.value_objects.idea import IdeaBrief
from ai_video_factory.errors import AppError
from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.infrastructure.story.idea_generator import IdeaGenerator
from ai_video_factory.infrastructure.story.writer import write_ideas_json
from ai_video_factory.interface.presenters.idea_presenter import render_ideas

_console = Console()


def idea_command(
    topic: Annotated[str, typer.Option("--topic", help="Story topic.")],
    style: Annotated[str, typer.Option("--style", help="Narrative style.")],
    platform: Annotated[str, typer.Option("--platform", help="Target platform, e.g. tiktok.")],
    language: Annotated[str, typer.Option("--language", help="Output language.")] = "vi",
) -> None:
    """Generate story ideas with the configured AI provider."""
    brief = IdeaBrief(topic=topic, style=style, target_platform=platform, language=language)
    settings = load_settings()
    try:
        generator = IdeaGenerator.from_settings(settings)
        ideas = asyncio.run(generator.generate(brief))
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    render_ideas(ideas)
    output_path = settings.app.output_dir / "ideas.json"
    write_ideas_json(output_path, brief, ideas)
    _console.print(f"[green]Saved[/green] {len(ideas)} ideas to {output_path}")
