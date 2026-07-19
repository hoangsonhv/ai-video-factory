"""Terminal presenter for a completed pipeline run (interface layer)."""

from __future__ import annotations

from rich.table import Table

from ai_video_factory.infrastructure.pipeline.models import PipelineResult
from ai_video_factory.interface.presenters.console_io import emit_renderable


def render_pipeline_summary(result: PipelineResult) -> None:
    """Render a summary of the pipeline outputs (files written)."""
    table = Table(title="Pipeline Complete")
    table.add_column("Stage", style="bold")
    table.add_column("Output", overflow="fold")
    table.add_column("Detail")
    table.add_row("Ideas", str(result.outputs[0]), f"{len(result.ideas)} ideas")
    table.add_row(
        "Outline", str(result.outputs[1]), f"{len(result.outline.chapter_outlines)} chapters"
    )
    table.add_row(
        "Chapter", str(result.outputs[2]), f"~{result.chapter.estimated_duration_seconds}s"
    )
    table.add_row("Image prompts", str(result.outputs[3]), f"{len(result.image_prompts)} prompts")
    emit_renderable(table)
