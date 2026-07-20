"""Terminal presenter for the AI Director stage (interface layer)."""

from __future__ import annotations

from pathlib import Path

from rich.table import Table

from ai_video_factory.domain.value_objects.director import DirectedMovie
from ai_video_factory.infrastructure.director.report import DirectionReport
from ai_video_factory.interface.presenters.console_io import emit_renderable


def render_direction_report(report: DirectionReport, path: Path) -> None:
    """Render the final tally of a direction run."""
    table = Table(title="Direction Report", show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value", overflow="fold")
    table.add_row("Directed", f"[green]{report.directed}[/green]")
    if report.skipped:
        table.add_row("Skipped (already done)", str(report.skipped))
    failed_style = "red" if report.failed else "green"
    table.add_row("Failed", f"[{failed_style}]{report.failed}[/{failed_style}]")
    table.add_row("Retry count", str(report.retries))
    if report.failed_scene_ids:
        table.add_row(
            "Failed scenes", ", ".join(str(scene_id) for scene_id in report.failed_scene_ids)
        )
    table.add_row("File", str(path))
    emit_renderable(table)


def render_shot_list(movie: DirectedMovie, path: Path) -> None:
    """Render the shot plan, one row per scene."""
    table = Table(title=f"Shot List — {path} ({movie.shot_count} shots)")
    table.add_column("Scene", justify="right", style="bold")
    table.add_column("Shots", justify="right")
    table.add_column("Planned", justify="right")
    table.add_column("Cameras", overflow="fold")
    table.add_column("Opening action", overflow="fold")
    for scene in movie.scenes:
        if not scene.is_planned:
            table.add_row(str(scene.id), "-", f"{scene.duration}s", "[red]unplanned[/red]", "-")
            continue
        cameras = ", ".join(dict.fromkeys(shot.camera for shot in scene.shots if shot.camera))
        table.add_row(
            str(scene.id),
            str(len(scene.shots)),
            f"{scene.shot_seconds}s/{scene.duration}s",
            cameras or "-",
            scene.shots[0].action or "-",
        )
    emit_renderable(table)
