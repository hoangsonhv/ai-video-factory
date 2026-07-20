"""``ai-video-factory tts`` CLI command (interface layer).

Reads the chapter narration, synthesizes it with the configured speech provider
(showing a Rich spinner), and saves the audio plus its metadata. All synthesis
logic lives in the infrastructure speech provider layer.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ai_video_factory.errors import AppError
from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.infrastructure.media.audio_storage import AudioStorage
from ai_video_factory.infrastructure.providers.speech.base.models import (
    SpeechSynthesisRequest,
    SpeechSynthesisResponse,
)
from ai_video_factory.infrastructure.providers.speech.base.provider import SpeechProvider
from ai_video_factory.infrastructure.providers.speech.base.writer import write_audio_metadata
from ai_video_factory.infrastructure.providers.speech.factory.speech_provider_factory import (
    SpeechProviderFactory,
)
from ai_video_factory.infrastructure.story.reader import read_chapter
from ai_video_factory.interface.presenters.tts_presenter import render_tts_summary

_console = Console()
_NARRATION_FILENAME = "narration.mp3"


def _ensure_utf8_stdout() -> None:
    """Switch stdout to UTF-8 so Vietnamese narration text and the Rich progress
    glyphs render on legacy (cp1252) Windows consoles instead of crashing."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    with contextlib.suppress(ValueError, OSError):  # stream may not be reconfigurable
        reconfigure(encoding="utf-8", errors="backslashreplace")


def _synthesize_with_progress(
    provider: SpeechProvider, request: SpeechSynthesisRequest
) -> SpeechSynthesisResponse:
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=_console,
    ) as progress:
        progress.add_task("Synthesizing narration", total=None)
        return asyncio.run(provider.synthesize(request))


def tts_command(
    input_path: Annotated[
        Path,
        typer.Option("--input", "--chapter", help="Path to a chapter JSON file."),
    ],
    language: Annotated[str, typer.Option("--language", help="Narration language.")] = "vi",
    force: Annotated[
        bool, typer.Option("--force", help="Regenerate even if the audio already exists.")
    ] = False,
) -> None:
    """Synthesize narration audio from a chapter with the configured provider."""
    _ensure_utf8_stdout()
    settings = load_settings()
    audio_dir = settings.app.output_dir / "audio"
    narration_path = audio_dir / _NARRATION_FILENAME
    if narration_path.exists() and not force:
        _console.print(
            f"[yellow]Skipped[/yellow] {narration_path} already exists (use --force to regenerate)."
        )
        return

    storage = AudioStorage(audio_dir)
    try:
        story_chapter = read_chapter(input_path)
        provider = SpeechProviderFactory.create(settings, storage)
        request = SpeechSynthesisRequest(text=story_chapter.content, language=language)
        response = _synthesize_with_progress(provider, request)
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    write_audio_metadata(audio_dir / "metadata.json", response)
    render_tts_summary(response)
    _console.print(f"[green]Saved[/green] narration to {response.audio_path}")
