"""Terminal presenter for generated image prompts (interface layer)."""

from __future__ import annotations

from rich.table import Table

from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.interface.presenters.console_io import emit_renderable


def render_image_prompts(prompts: list[ImagePrompt]) -> None:
    """Render the image prompts as a Rich table (UTF-8-safe on legacy terminals)."""
    style = prompts[0].style if prompts else "-"
    aspect_ratio = prompts[0].aspect_ratio if prompts else "-"
    table = Table(title=f"Image Prompts (style={style}, aspect={aspect_ratio})")
    table.add_column("#", justify="right")
    table.add_column("Prompt", overflow="fold")
    table.add_column("Camera")
    table.add_column("Lighting")
    table.add_column("Environment", overflow="fold")
    for image in prompts:
        table.add_row(
            str(image.scene_number),
            image.prompt,
            image.camera,
            image.lighting,
            image.environment,
        )
    emit_renderable(table)
