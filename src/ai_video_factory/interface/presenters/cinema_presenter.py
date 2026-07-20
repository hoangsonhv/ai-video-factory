"""Terminal presenters for the cinematic director (interface layer)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from rich.table import Table

from ai_video_factory.domain.value_objects.cinema import CinematicDirection
from ai_video_factory.interface.presenters.console_io import emit_renderable


def render_shot_list(direction: CinematicDirection, path: Path) -> None:
    """Render the coverage, one row per shot."""
    table = Table(title=f"Cinematic Direction - {path}")
    table.add_column("Shot", justify="right", style="bold")
    table.add_column("Beat")
    table.add_column("Shot type")
    table.add_column("Angle")
    table.add_column("Lens", justify="right")
    table.add_column("Composition")
    table.add_column("Action", overflow="fold")
    beats = {scene.scene_id: scene.story_beat.value for scene in direction.scenes}
    for shot in direction.shots:
        table.add_row(
            str(shot.shot_id),
            beats.get(shot.scene_id, "-"),
            shot.shot_type.value,
            shot.camera_angle.value,
            shot.lens.value,
            shot.composition.value,
            shot.action,
        )
    emit_renderable(table)


def render_coverage(direction: CinematicDirection) -> None:
    """Render how varied the coverage is — the point of directing at all."""
    lenses = Counter(shot.lens.value for shot in direction.shots)
    shots = Counter(shot.shot_type.value for shot in direction.shots)
    angles = Counter(shot.camera_angle.value for shot in direction.shots)

    table = Table(title="Coverage", show_header=False)
    table.add_column("Axis", style="bold")
    table.add_column("Distribution", overflow="fold")
    for label, counts in (("Lenses", lenses), ("Shot types", shots), ("Angles", angles)):
        table.add_row(label, ", ".join(f"{name} x{count}" for name, count in counts.most_common()))
    emit_renderable(table)
