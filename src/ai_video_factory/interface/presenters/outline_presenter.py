"""Terminal presenter for a generated story outline (interface layer)."""

from __future__ import annotations

from rich.console import Group
from rich.table import Table

from ai_video_factory.domain.value_objects.outline import StoryOutline
from ai_video_factory.interface.presenters.console_io import emit_renderable


def render_outline(outline: StoryOutline) -> None:
    """Render the outline (metadata + chapters) as UTF-8-safe Rich tables."""
    meta = Table(title="Story Outline", show_header=False)
    meta.add_column("Field", style="bold")
    meta.add_column("Value", overflow="fold")
    meta.add_row("Title", outline.title)
    meta.add_row("Genre", outline.genre)
    meta.add_row("World setting", outline.world_setting)
    meta.add_row("Cultivation system", outline.cultivation_system)
    meta.add_row("Main character", outline.main_character)
    meta.add_row("Supporting", ", ".join(outline.supporting_characters))
    meta.add_row("Antagonist", outline.antagonist)
    meta.add_row("Story arc", outline.story_arc)
    meta.add_row("Ending", outline.ending)

    chapters = Table(title=f"Chapters ({len(outline.chapter_outlines)})")
    chapters.add_column("#", justify="right")
    chapters.add_column("Title", style="bold")
    chapters.add_column("Summary", overflow="fold")
    chapters.add_column("Cliffhanger", overflow="fold")
    for chapter in outline.chapter_outlines:
        chapters.add_row(
            str(chapter.chapter_number), chapter.title, chapter.summary, chapter.cliffhanger
        )

    emit_renderable(Group(meta, chapters))
