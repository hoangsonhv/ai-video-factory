"""Terminal presenter for a generated story chapter (interface layer)."""

from __future__ import annotations

from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from ai_video_factory.domain.value_objects.chapter import StoryChapter
from ai_video_factory.interface.presenters.console_io import emit_renderable


def render_chapter(chapter: StoryChapter) -> None:
    """Render the chapter (metadata + prose) as UTF-8-safe Rich output."""
    meta = Table(title="Story Chapter", show_header=False)
    meta.add_column("Field", style="bold")
    meta.add_column("Value", overflow="fold")
    meta.add_row("Title", chapter.title)
    meta.add_row("Estimated duration", f"{chapter.estimated_duration_seconds}s")
    meta.add_row("Word count", str(len(chapter.content.split())))

    content = Panel(chapter.content, title="Content")
    emit_renderable(Group(meta, content))
