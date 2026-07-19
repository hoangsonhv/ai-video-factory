"""CLI application (interface layer).

Thin Typer commands following the delivery rule: parse → invoke → present.
Diagnostic and configuration logic lives in the infrastructure layer; the CLI
only wires those pieces to the terminal (docs/ai-tool.md §2.4).
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console

from ai_video_factory import __version__
from ai_video_factory.errors import ConfigurationError
from ai_video_factory.infrastructure.config.settings import LoggingSettings, load_settings
from ai_video_factory.infrastructure.diagnostics import run_all_checks
from ai_video_factory.infrastructure.logging.setup import configure_logging
from ai_video_factory.interface.cli.chapter_commands import chapter_command
from ai_video_factory.interface.cli.generate_commands import generate_command
from ai_video_factory.interface.cli.idea_commands import idea_command
from ai_video_factory.interface.cli.image_commands import image_command
from ai_video_factory.interface.cli.image_prompt_commands import image_prompt_command
from ai_video_factory.interface.cli.outline_commands import outline_command
from ai_video_factory.interface.cli.prompt_commands import prompt_app
from ai_video_factory.interface.presenters.diagnostics_presenter import render_diagnostics

app = typer.Typer(add_completion=False, help="AI Video Factory command-line interface.")
app.add_typer(prompt_app, name="prompt")
app.command("generate")(generate_command)
app.command("idea")(idea_command)
app.command("outline")(outline_command)
app.command("chapter")(chapter_command)
app.command("image-prompt")(image_prompt_command)
app.command("image")(image_command)
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
def doctor() -> None:
    """Check that the runtime environment is ready.

    Verifies the Python version, ffmpeg availability, a writable output
    folder, configuration loading and SQLite connectivity. Exits with a
    non-zero status if any check fails.
    """
    _logger.debug("Running doctor diagnostics")
    results = run_all_checks()
    render_diagnostics(results, console=_console)
    if any(result.is_failure for result in results):
        raise typer.Exit(code=1)


def main() -> None:
    """Entry point for the ``factory`` console script."""
    app()
