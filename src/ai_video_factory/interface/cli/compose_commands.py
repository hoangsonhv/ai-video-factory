"""``ai-video-factory compose`` CLI command (interface layer).

Composes the final portrait MP4 from existing assets (images, narration audio,
subtitles) using ffmpeg. FFmpeg availability is verified up front with the same
diagnostics the ``doctor`` command uses. This command only *reads* the assets —
it never regenerates images, audio, or subtitles.
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
from ai_video_factory.infrastructure.asset_pipeline.models import AssetResult
from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.infrastructure.diagnostics import check_ffmpeg
from ai_video_factory.infrastructure.video.ffmpeg_composer import FfmpegVideoComposer
from ai_video_factory.infrastructure.video.writer import write_video_metadata
from ai_video_factory.interface.presenters.video_presenter import render_video_summary

_console = Console()
_VIDEO_FILENAME = "final.mp4"


def _ensure_utf8_stdout() -> None:
    """Switch stdout to UTF-8 so Vietnamese paths and Rich progress glyphs render
    on legacy (cp1252) Windows consoles instead of crashing."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    with contextlib.suppress(ValueError, OSError):  # stream may not be reconfigurable
        reconfigure(encoding="utf-8", errors="backslashreplace")


def _compose_with_progress(
    composer: FfmpegVideoComposer, assets: tuple[AssetResult, ...]
) -> AssetResult:
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=_console,
    ) as progress:
        progress.add_task("Composing video", total=None)
        return asyncio.run(composer.compose_video(*assets))


def compose_command(
    images: Annotated[Path, typer.Option("--images", help="Directory of generated images.")],
    audio: Annotated[Path, typer.Option("--audio", help="Path to the narration audio file.")],
    subtitle: Annotated[Path, typer.Option("--subtitle", help="Path to the subtitle .srt file.")],
) -> None:
    """Compose the final TikTok MP4 from existing images, audio, and subtitles."""
    _ensure_utf8_stdout()
    settings = load_settings()

    ffmpeg_status = check_ffmpeg()
    if ffmpeg_status.is_failure:
        _console.print(
            f"[red]Error:[/red] FFmpeg is required but was not found ({ffmpeg_status.detail}). "
            "Install FFmpeg and ensure it is on your PATH, then re-run."
        )
        raise typer.Exit(code=1)

    if not images.is_dir():
        _console.print(f"[red]Error:[/red] images directory not found: {images}")
        raise typer.Exit(code=1)
    if not audio.is_file():
        _console.print(f"[red]Error:[/red] audio file not found: {audio}")
        raise typer.Exit(code=1)
    if not subtitle.is_file():
        _console.print(f"[red]Error:[/red] subtitle file not found: {subtitle}")
        raise typer.Exit(code=1)

    video_dir = settings.app.output_dir / "video"
    output_path = video_dir / _VIDEO_FILENAME
    composer = FfmpegVideoComposer(settings.video, output_path)
    assets = (
        AssetResult(success=True, path=images),
        AssetResult(success=True, path=audio),
        AssetResult(success=True, path=subtitle),
    )
    try:
        result = _compose_with_progress(composer, assets)
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    write_video_metadata(video_dir / "metadata.json", result)
    render_video_summary(result, output_path)
    _console.print(f"[green]Saved[/green] video to {output_path}")
