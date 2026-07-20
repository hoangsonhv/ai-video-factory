"""Terminal presenters for the character memory stage (interface layer)."""

from __future__ import annotations

from pathlib import Path

from rich.table import Table

from ai_video_factory.domain.value_objects.character_memory import (
    AppearanceScoreDocument,
    CharacterMemoryDocument,
)
from ai_video_factory.interface.presenters.console_io import emit_renderable

_ISSUE_PREVIEW = 3


def render_memory(memory: CharacterMemoryDocument, path: Path) -> None:
    """Render what the film remembers about each character."""
    table = Table(title=f"Character Memory - {path}")
    table.add_column("Character", style="bold")
    table.add_column("Reference", overflow="fold")
    table.add_column("Hash")
    table.add_column("Canonical appearance", overflow="fold")
    for character in memory.characters:
        reference = (
            Path(character.reference_image).name
            if character.reference_image
            else "[yellow]not adopted[/yellow]"
        )
        table.add_row(
            character.character_id,
            reference,
            character.appearance_hash or "-",
            character.summary or "-",
        )
    emit_renderable(table)


def render_appearance_scores(scores: AppearanceScoreDocument, path: Path) -> None:
    """Render one row per prompt, naming what the appearance failed to pin."""
    table = Table(
        title=(
            f"Appearance Scores - {path} (average {scores.average}, threshold {scores.threshold})"
        )
    )
    table.add_column("Shot", justify="right", style="bold")
    table.add_column("Character")
    table.add_column("Hair", justify="right")
    table.add_column("Face", justify="right")
    table.add_column("Clothes", justify="right")
    table.add_column("Weapon", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Missing", overflow="fold")
    for score in scores.scores:
        style = "green" if score.passed(scores.threshold) else "red"
        issues = ", ".join(score.issues[:_ISSUE_PREVIEW])
        if len(score.issues) > _ISSUE_PREVIEW:
            issues += f" (+{len(score.issues) - _ISSUE_PREVIEW})"
        table.add_row(
            str(score.shot_id),
            score.character_id or "-",
            str(score.hair),
            str(score.face),
            str(score.clothes),
            str(score.weapon),
            f"[{style}]{score.total}[/{style}]",
            issues or "-",
        )
    emit_renderable(table)
