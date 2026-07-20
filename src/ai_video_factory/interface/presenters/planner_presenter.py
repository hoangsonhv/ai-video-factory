"""Terminal presenters for the shot planner (interface layer)."""

from __future__ import annotations

from pathlib import Path

from rich.table import Table

from ai_video_factory.domain.value_objects.shot_plan import ShotPlan, ShotStatistics
from ai_video_factory.interface.presenters.console_io import emit_renderable


def render_shot_plan(plan: ShotPlan, path: Path) -> None:
    """Render the plan, one row per shot."""
    table = Table(title=f"Shot Plan - {path}")
    table.add_column("Shot", justify="right", style="bold")
    table.add_column("Scene kind")
    table.add_column("Shot type")
    table.add_column("Distance")
    table.add_column("Angle")
    table.add_column("Lens", justify="right")
    table.add_column("Body visible")
    table.add_column("Background", overflow="fold")

    for shot in plan.shots:
        kind = plan.scene_kinds.get(shot.scene_id)
        table.add_row(
            str(shot.shot_id),
            kind.value if kind else "-",
            shot.shot_type.value,
            shot.camera_distance.value,
            shot.camera_angle.value,
            shot.lens.value,
            shot.visible_body.value,
            shot.environment_visibility.background or "[red]none[/red]",
        )
    emit_renderable(table)


def render_statistics(statistics: ShotStatistics) -> None:
    """Render the four histograms the sprint asks for."""
    table = Table(title="Shot Statistics", show_header=False)
    table.add_column("Axis", style="bold")
    table.add_column("Distribution", overflow="fold")
    for label, counts in (
        ("Shot types", statistics.shot_types),
        ("Lenses", statistics.lenses),
        ("Camera angles", statistics.cameras),
        ("Body visibility", statistics.body_visibility),
    ):
        table.add_row(label, ", ".join(f"{name} x{count}" for name, count in counts.items()))
    emit_renderable(table)


def render_distribution(plan: ShotPlan) -> None:
    """Render whether the coverage is inside its bounds, and how it got there."""
    report = plan.distribution
    table = Table(title="Coverage Validation", show_header=False)
    table.add_column("Rule", style="bold")
    table.add_column("Measured")
    table.add_row("close <= 20%", _verdict(report.close_pct, report.close_pct <= 20.0))
    table.add_row("medium 20-35%", _verdict(report.medium_pct, 20.0 <= report.medium_pct <= 35.0))
    table.add_row("wide / full body >= 40%", _verdict(report.wide_pct, report.wide_pct >= 40.0))
    table.add_row(
        "establishing >= 5%", _verdict(report.establishing_pct, report.establishing_pct >= 5.0)
    )
    table.add_row("re-plans", str(plan.replans))
    emit_renderable(table)


def _verdict(percentage: float, passed: bool) -> str:
    colour = "green" if passed else "red"
    return f"[{colour}]{percentage}%[/{colour}]"
