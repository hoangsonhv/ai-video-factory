"""``ai-video-factory subtitle`` CLI command (interface layer).

Transcribes the narration audio (aligned to the chapter text) with the
configured transcription provider and writes a synchronized ``.srt`` file. All
transcription logic lives in the infrastructure transcription provider layer.
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
from ai_video_factory.infrastructure.media.subtitle_storage import SubtitleStorage
from ai_video_factory.infrastructure.providers.transcription.base.models import (
    TranscriptionRequest,
    TranscriptionResult,
)
from ai_video_factory.infrastructure.providers.transcription.base.provider import (
    TranscriptionProvider,
)
from ai_video_factory.infrastructure.providers.transcription.base.srt import to_srt
from ai_video_factory.infrastructure.providers.transcription.factory.transcription_provider_factory import (  # noqa: E501
    TranscriptionProviderFactory,
)
from ai_video_factory.infrastructure.story.reader import read_chapter
from ai_video_factory.interface.presenters.subtitle_presenter import render_subtitle_summary

_console = Console()
_SUBTITLE_FILENAME = "narration.srt"


def _ensure_utf8_stdout() -> None:
    """Switch stdout to UTF-8 so Vietnamese text and Rich progress glyphs render
    on legacy (cp1252) Windows consoles instead of crashing."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    with contextlib.suppress(ValueError, OSError):  # stream may not be reconfigurable
        reconfigure(encoding="utf-8", errors="backslashreplace")


def _transcribe_with_progress(
    provider: TranscriptionProvider, request: TranscriptionRequest
) -> TranscriptionResult:
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=_console,
    ) as progress:
        progress.add_task("Generating subtitles", total=None)
        return asyncio.run(provider.transcribe(request))


def subtitle_command(
    audio: Annotated[Path, typer.Option("--audio", help="Path to the narration audio file.")],
    chapter: Annotated[Path, typer.Option("--chapter", help="Path to the chapter JSON file.")],
    language: Annotated[str, typer.Option("--language", help="Subtitle language.")] = "vi",
    force: Annotated[
        bool, typer.Option("--force", help="Regenerate even if the subtitle already exists.")
    ] = False,
) -> None:
    """Generate a synchronized ``.srt`` subtitle from narration audio and a chapter."""
    _ensure_utf8_stdout()
    settings = load_settings()
    subtitles_dir = settings.app.output_dir / "subtitles"
    srt_path = subtitles_dir / _SUBTITLE_FILENAME
    if srt_path.exists() and not force:
        _console.print(
            f"[yellow]Skipped[/yellow] {srt_path} already exists (use --force to regenerate)."
        )
        return

    if not audio.is_file():
        _console.print(f"[red]Error:[/red] audio file not found: {audio}")
        raise typer.Exit(code=1)

    storage = SubtitleStorage(subtitles_dir)
    try:
        story_chapter = read_chapter(chapter)
        provider = TranscriptionProviderFactory.create(settings)
        request = TranscriptionRequest(
            audio_path=audio, language=language, reference_text=story_chapter.content
        )
        result = _transcribe_with_progress(provider, request)
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    path = storage.save(to_srt(result.segments))
    render_subtitle_summary(result, path)
    _console.print(f"[green]Saved[/green] subtitles to {path}")
