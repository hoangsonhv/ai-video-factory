"""Terminal presenter for generated subtitles (interface layer)."""

from __future__ import annotations

from pathlib import Path

from rich.table import Table

from ai_video_factory.infrastructure.providers.transcription.base.models import TranscriptionResult
from ai_video_factory.interface.presenters.console_io import emit_renderable


def render_subtitle_summary(result: TranscriptionResult, path: Path) -> None:
    """Render a summary of the generated subtitle file."""
    table = Table(title="Subtitles Generated", show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value", overflow="fold")
    table.add_row("File", str(path))
    table.add_row("Provider", result.provider)
    table.add_row("Language", result.language)
    table.add_row("Segments", str(len(result.segments)))
    table.add_row("Duration", f"{result.duration_seconds:.2f}s")
    emit_renderable(table)
