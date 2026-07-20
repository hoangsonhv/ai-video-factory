"""CLI application (interface layer).

Thin Typer commands following the delivery rule: parse → invoke → present.
Diagnostic and configuration logic lives in the infrastructure layer; the CLI
only wires those pieces to the terminal (docs/ai-tool.md §2.4).
"""

from __future__ import annotations

import logging
from typing import Annotated

import typer
from rich.console import Console

from ai_video_factory import __version__
from ai_video_factory.errors import ConfigurationError
from ai_video_factory.infrastructure.config.settings import LoggingSettings, load_settings
from ai_video_factory.infrastructure.diagnostics import run_all_checks, run_image_checks
from ai_video_factory.infrastructure.logging.setup import configure_logging
from ai_video_factory.interface.cli.assets_commands import assets_command
from ai_video_factory.interface.cli.chapter_commands import chapter_command
from ai_video_factory.interface.cli.character_commands import character_app
from ai_video_factory.interface.cli.cinema_commands import cinema_command
from ai_video_factory.interface.cli.compose_commands import compose_command
from ai_video_factory.interface.cli.continuity_commands import continuity_command
from ai_video_factory.interface.cli.director_commands import director_command
from ai_video_factory.interface.cli.generate_commands import generate_command
from ai_video_factory.interface.cli.idea_commands import idea_command
from ai_video_factory.interface.cli.image_commands import image_command, image_models_command
from ai_video_factory.interface.cli.image_prompt_commands import image_prompt_command
from ai_video_factory.interface.cli.movie_commands import movie_command
from ai_video_factory.interface.cli.outline_commands import outline_command
from ai_video_factory.interface.cli.planner_commands import shot_plan_command
from ai_video_factory.interface.cli.prompt_commands import prompt_app
from ai_video_factory.interface.cli.storyboard_commands import storyboard_command
from ai_video_factory.interface.cli.subtitle_commands import subtitle_command
from ai_video_factory.interface.cli.tts_commands import tts_command
from ai_video_factory.interface.cli.video_commands import video_app
from ai_video_factory.interface.presenters.diagnostics_presenter import render_diagnostics

app = typer.Typer(add_completion=False, help="AI Video Factory command-line interface.")
app.add_typer(prompt_app, name="prompt")
app.add_typer(character_app, name="character")
app.add_typer(video_app, name="video")
app.command("generate")(generate_command)
app.command("idea")(idea_command)
app.command("outline")(outline_command)
app.command("chapter")(chapter_command)
app.command("image-prompt")(image_prompt_command)
app.command("movie")(movie_command)
app.command("director")(director_command)
app.command("storyboard")(storyboard_command)
app.command("continuity")(continuity_command)
app.command("cinema")(cinema_command)
app.command("shot-plan")(shot_plan_command)
app.command("image")(image_command)
app.command("image-models")(image_models_command)
app.command("tts")(tts_command)
app.command("subtitle")(subtitle_command)
app.command("compose")(compose_command)
app.command("assets")(assets_command)
_console = Console()
_logger = logging.getLogger(__name__)


@app.callback()
def _bootstrap() -> None:
    """Configure logging before any command runs.

    Uses the configured logging settings when available, falling back to
    defaults if configuration is invalid so the CLI itself never fails to
    start over a bad config (the ``doctor`` command reports the problem).
    """
    try:
        settings = load_settings()
        configure_logging(settings.logging)
    except ConfigurationError:
        configure_logging(LoggingSettings())


@app.command()
def version() -> None:
    """Print the application version."""
    _console.print(f"AI Video Factory {__version__}")


@app.command()
def doctor(
    image: Annotated[
        bool,
        typer.Option("--image", help="Run image-provider diagnostics instead of the general ones."),
    ] = False,
) -> None:
    """Check that the runtime environment is ready.

    Verifies the Python version, ffmpeg availability, a writable output
    folder, configuration loading and SQLite connectivity. With ``--image``,
    runs image-provider diagnostics instead (model, provider, region, auth,
    API reachability, model existence and a live quota probe). Exits with a
    non-zero status if any check fails.
    """
    _logger.debug("Running doctor diagnostics (image=%s)", image)
    results = run_image_checks() if image else run_all_checks()
    render_diagnostics(results, console=_console)
    if any(result.is_failure for result in results):
        raise typer.Exit(code=1)


def main() -> None:
    """Entry point for the ``factory`` console script."""
    app()
