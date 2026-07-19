"""Terminal presenter for the asset pipeline status (interface layer)."""

from __future__ import annotations

from rich.table import Table

from ai_video_factory.infrastructure.asset_pipeline.models import AssetStage
from ai_video_factory.interface.presenters.console_io import emit_renderable


def render_asset_status(stages: list[AssetStage]) -> None:
    """Render the readiness of each asset pipeline stage."""
    table = Table(title="Asset Pipeline")
    table.add_column("Stage", style="bold")
    table.add_column("Backend")
    table.add_column("Status")
    for stage in stages:
        status = "[green]ready[/green]" if stage.ready else "[yellow]pending[/yellow]"
        table.add_row(stage.name, stage.backend, status)
    emit_renderable(table)
