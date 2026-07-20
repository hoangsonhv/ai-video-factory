"""Terminal presenter for the storyboard (interface layer)."""

from __future__ import annotations

from pathlib import Path

from rich.table import Table

from ai_video_factory.domain.value_objects.storyboard import Storyboard
from ai_video_factory.interface.presenters.console_io import emit_renderable

_PREVIEW_CHARS = 48


def render_storyboard(storyboard: Storyboard, path: Path) -> None:
    """Render the timeline, one row per shot."""
    table = Table(
        title=(
            f"Storyboard - {path} "
            f"({storyboard.shot_count} shots / {storyboard.scene_count} scenes, "
            f"{storyboard.total_duration:.1f}s)"
        )
    )
    table.add_column("#", justify="right", style="bold")
    table.add_column("Scene", justify="right")
    table.add_column("Time", justify="right")
    table.add_column("Camera", overflow="fold")
    table.add_column("Action", overflow="fold")
    table.add_column("Subtitle", overflow="fold")
    for shot in storyboard.shots:
        subtitle = shot.subtitle
        if len(subtitle) > _PREVIEW_CHARS:
            subtitle = subtitle[:_PREVIEW_CHARS].rstrip() + "..."
        table.add_row(
            str(shot.id),
            f"{shot.scene_id}.{shot.order}",
            f"{shot.speech_start:.1f}-{shot.speech_end:.1f}s",
            shot.camera or "-",
            shot.action or "-",
            subtitle or "-",
        )
    emit_renderable(table)
