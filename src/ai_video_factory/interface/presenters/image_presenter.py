"""Terminal presenter for image-generation results (interface layer)."""

from __future__ import annotations

from rich.table import Table

from ai_video_factory.interface.presenters.console_io import emit_renderable


def render_image_run_summary(*, generated: int, skipped: int, failed: int) -> None:
    """Render the final generated / skipped / failed summary as a table."""
    table = Table(title="Image Generation Summary")
    table.add_column("Result")
    table.add_column("Count", justify="right")
    table.add_row("[green]Generated[/green]", str(generated))
    table.add_row("[yellow]Skipped[/yellow]", str(skipped))
    table.add_row("[red]Failed[/red]", str(failed))
    emit_renderable(table)
