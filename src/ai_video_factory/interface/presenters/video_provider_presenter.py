"""Terminal presenters for the video provider layer (interface layer)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from rich.table import Table

from ai_video_factory.infrastructure.video.providers.base.models import (
    VideoGenerationResult,
    VideoJobStatus,
    VideoProviderStatus,
)
from ai_video_factory.infrastructure.video.providers.cost import GenerationPlan
from ai_video_factory.interface.presenters.console_io import emit_renderable
from ai_video_factory.shared.health import HealthStatus

_HEALTH_STYLE = {
    HealthStatus.OK: "green",
    HealthStatus.WARN: "yellow",
    HealthStatus.FAIL: "red",
}


def render_provider_list(statuses: Sequence[VideoProviderStatus]) -> None:
    """Render the registered video providers and their models."""
    table = Table(title="Video Providers")
    table.add_column("Provider", style="bold")
    table.add_column("Default", justify="center")
    table.add_column("Models", overflow="fold")
    for status in statuses:
        table.add_row(
            status.name,
            "[green]yes[/green]" if status.is_default else "no",
            ", ".join(status.models) or "-",
        )
    emit_renderable(table)


def render_provider_health(statuses: Sequence[VideoProviderStatus]) -> None:
    """Render one health row per registered video provider."""
    table = Table(title="Video Providers - Doctor")
    table.add_column("Provider", style="bold")
    table.add_column("Default", justify="center")
    table.add_column("Status")
    table.add_column("Detail", overflow="fold")
    for status in statuses:
        style = _HEALTH_STYLE[status.health.status]
        table.add_row(
            status.name,
            "[green]yes[/green]" if status.is_default else "no",
            f"[{style}]{status.health.status.value}[/{style}]",
            status.health.detail,
        )
    emit_renderable(table)


def render_generation_plan(plan: GenerationPlan) -> None:
    """Render what a run would submit and cost, without submitting anything."""
    table = Table(title="Video Generation Plan (dry run)", show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value", overflow="fold")
    table.add_row("Provider", plan.provider)
    table.add_row("Model", plan.model)
    scenes = str(plan.scene_count)
    if plan.limited:
        scenes = f"{scenes} (limited to the first {plan.jobs})"
    table.add_row("Scenes", scenes)
    table.add_row("Estimated jobs", str(plan.jobs))
    table.add_row("Estimated duration", f"{plan.total_duration:.1f}s")
    if plan.cost_is_known:
        cost = f"{plan.estimated_cost:.2f}"
    else:
        cost = "unknown (set AIVF_VIDEO_PROVIDER__COST_PER_SECOND)"
    table.add_row("Estimated cost", cost)
    table.add_row("Paid", "[red]yes[/red]" if plan.is_paid else "[green]no (local mock)[/green]")
    emit_renderable(table)


def render_generation_summary(results: Sequence[VideoGenerationResult], output_dir: Path) -> None:
    """Render one row per scene and where the clips were written."""
    table = Table(title=f"Video Clips - {output_dir}")
    table.add_column("Scene", justify="right", style="bold")
    table.add_column("Status")
    table.add_column("Duration", justify="right")
    table.add_column("File", overflow="fold")
    for result in results:
        style = "green" if result.is_completed else "red"
        duration = f"{result.duration:.1f}s" if result.duration else "-"
        filename = result.video_path.name if result.video_path else "-"
        table.add_row(
            str(result.scene_id),
            f"[{style}]{result.status.value}[/{style}]",
            duration,
            filename,
        )
    emit_renderable(table)


def count_by_status(results: Sequence[VideoGenerationResult], status: VideoJobStatus) -> int:
    """How many results carry ``status``."""
    return sum(1 for result in results if result.status is status)
