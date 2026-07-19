"""``ai-video-factory generate`` CLI command (interface layer).

Runs the full Phase-1 pipeline (idea → outline → chapter → image prompts) with a
Rich progress display. Orchestration lives in the infrastructure pipeline
runner; this command only wires inputs, progress, and the summary.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn

from ai_video_factory.errors import AppError
from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.infrastructure.pipeline.models import PipelineRequest, PipelineResult
from ai_video_factory.infrastructure.pipeline.runner import PipelineRunner
from ai_video_factory.interface.presenters.pipeline_presenter import render_pipeline_summary

_console = Console()


def _run_with_progress(runner: PipelineRunner, request: PipelineRequest) -> PipelineResult:
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=_console,
    ) as progress:
        task = progress.add_task("Starting", total=4)

        def on_stage(number: int, total: int, name: str) -> None:
            progress.update(task, description=f"[{number}/{total}] {name}", completed=number - 1)

        result = asyncio.run(runner.run(request, on_stage=on_stage))
        progress.update(task, completed=4, description="Done")
        return result


def generate_command(
    topic: Annotated[str, typer.Option("--topic", help="Story topic.")],
    style: Annotated[str, typer.Option("--style", help="Narrative style.")],
    platform: Annotated[str, typer.Option("--platform", help="Target platform, e.g. tiktok.")],
    chapters: Annotated[int, typer.Option("--chapters", help="Number of chapters.")] = 10,
) -> None:
    """Run the pipeline from a topic through to image prompts (no images)."""
    settings = load_settings()
    request = PipelineRequest(
        topic=topic, style=style, target_platform=platform, chapter_count=chapters
    )
    try:
        runner = PipelineRunner.from_settings(settings)
        result = _run_with_progress(runner, request)
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    render_pipeline_summary(result)
    _console.print(f"[green]Done.[/green] Outputs in {settings.app.output_dir}")
