"""Terminal presenter for the composed video (interface layer)."""

from __future__ import annotations

from pathlib import Path

from rich.table import Table

from ai_video_factory.infrastructure.asset_pipeline.models import AssetResult
from ai_video_factory.interface.presenters.console_io import emit_renderable


def render_video_summary(result: AssetResult, path: Path) -> None:
    """Render a summary of the composed final video."""
    table = Table(title="Video Composed", show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value", overflow="fold")
    table.add_row("File", str(path))
    table.add_row("Resolution", str(result.metadata.get("resolution", "")))
    table.add_row("FPS", str(result.metadata.get("fps", "")))
    table.add_row("Duration", f"{result.duration:.2f}s")
    table.add_row("Images", str(result.metadata.get("image_count", "")))
    table.add_row("Subtitles", str(result.metadata.get("subtitle_count", "")))
    emit_renderable(table)
