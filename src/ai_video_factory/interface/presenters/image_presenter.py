"""Terminal presenter for generated-image results (interface layer)."""

from __future__ import annotations

from rich.table import Table

from ai_video_factory.infrastructure.providers.image.base.models import ImageGenerationResponse
from ai_video_factory.interface.presenters.console_io import emit_renderable


def render_image_summary(responses: list[ImageGenerationResponse]) -> None:
    """Render a summary table of the generated images."""
    table = Table(title="Generated Images")
    table.add_column("#", justify="right")
    table.add_column("Path", overflow="fold")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Time (s)", justify="right")
    for index, response in enumerate(responses, start=1):
        table.add_row(
            str(index),
            str(response.image_path),
            response.provider,
            response.model,
            f"{response.generation_time:.2f}",
        )
    emit_renderable(table)
