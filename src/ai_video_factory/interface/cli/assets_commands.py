"""``ai-video-factory assets`` CLI command (interface layer).

Shows the asset pipeline status — which stages are ready and which are pending.
It does not run any generation.
"""

from __future__ import annotations

import typer
from rich.console import Console

from ai_video_factory.errors import AppError
from ai_video_factory.infrastructure.asset_pipeline.runner import AssetPipelineRunner
from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.interface.presenters.assets_presenter import render_asset_status

_console = Console()


def assets_command() -> None:
    """Show the asset pipeline status (image, voice, subtitles, video)."""
    settings = load_settings()
    try:
        runner = AssetPipelineRunner.from_settings(settings)
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    render_asset_status(runner.stage_status())
