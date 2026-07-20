"""Terminal presenter for the visual continuity stage (interface layer)."""

from __future__ import annotations

from pathlib import Path

from rich.table import Table

from ai_video_factory.domain.value_objects.continuity import PromptScoreDocument
from ai_video_factory.interface.presenters.console_io import emit_renderable

_ISSUE_PREVIEW = 3


def render_scores(scores: PromptScoreDocument, path: Path) -> None:
    """Render one row per prompt, with the dimension that let it down."""
    table = Table(
        title=(
            f"Prompt Continuity Scores - {path} "
            f"(average {scores.average}, threshold {scores.threshold})"
        )
    )
    table.add_column("Shot", justify="right", style="bold")
    table.add_column("Char", justify="right")
    table.add_column("Env", justify="right")
    table.add_column("Style", justify="right")
    table.add_column("Story", justify="right")
    table.add_column("Cam", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Missing", overflow="fold")
    for score in scores.scores:
        style = "green" if score.passed(scores.threshold) else "red"
        issues = ", ".join(score.issues[:_ISSUE_PREVIEW])
        if len(score.issues) > _ISSUE_PREVIEW:
            issues += f" (+{len(score.issues) - _ISSUE_PREVIEW})"
        table.add_row(
            str(score.shot_id),
            str(score.character_consistency),
            str(score.environment_consistency),
            str(score.style_consistency),
            str(score.story_continuity),
            str(score.camera_continuity),
            f"[{style}]{score.total}[/{style}]",
            issues or "-",
        )
    emit_renderable(table)
