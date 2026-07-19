"""Terminal presenter for generated story ideas (interface layer)."""

from __future__ import annotations

from rich.table import Table

from ai_video_factory.domain.value_objects.idea import StoryIdea
from ai_video_factory.interface.presenters.console_io import emit_renderable


def render_ideas(ideas: list[StoryIdea]) -> None:
    """Render the ideas as a Rich table (UTF-8-safe on legacy terminals)."""
    table = Table(title="Story Ideas")
    table.add_column("#", justify="right")
    table.add_column("Title", style="bold")
    table.add_column("Hook", overflow="fold")
    table.add_column("Summary", overflow="fold")
    table.add_column("Tags")
    for index, idea in enumerate(ideas, start=1):
        table.add_row(str(index), idea.title, idea.hook, idea.summary, ", ".join(idea.tags))
    emit_renderable(table)
