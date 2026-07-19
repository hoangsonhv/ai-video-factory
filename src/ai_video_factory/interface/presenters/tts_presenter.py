"""Terminal presenter for synthesized narration (interface layer)."""

from __future__ import annotations

from rich.table import Table

from ai_video_factory.infrastructure.providers.speech.base.models import SpeechSynthesisResponse
from ai_video_factory.interface.presenters.console_io import emit_renderable


def render_tts_summary(response: SpeechSynthesisResponse) -> None:
    """Render a summary of the synthesized narration."""
    table = Table(title="Narration Synthesized", show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value", overflow="fold")
    table.add_row("Audio", str(response.audio_path))
    table.add_row("Provider", response.provider)
    table.add_row("Voice", response.voice)
    table.add_row("Duration", f"{response.duration_seconds:.2f}s")
    table.add_row("Sample rate", f"{response.sample_rate} Hz")
    emit_renderable(table)
