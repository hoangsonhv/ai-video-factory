"""``ai-video-factory image`` CLI command (interface layer).

Reads image prompts, generates every image with the configured provider
(showing a Rich progress bar), and saves them under ``output/images/``.
All generation logic lives in the infrastructure image provider layer.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress

from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.errors import AppError
from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.infrastructure.media.image_storage import ImageStorage
from ai_video_factory.infrastructure.providers.image.base.models import (
    ImageGenerationRequest,
    ImageGenerationResponse,
)
from ai_video_factory.infrastructure.providers.image.base.provider import ImageProvider
from ai_video_factory.infrastructure.providers.image.factory.image_provider_factory import (
    ImageProviderFactory,
)
from ai_video_factory.infrastructure.story.reader import read_image_prompts
from ai_video_factory.interface.presenters.image_presenter import render_image_summary

_console = Console()


def _to_request(prompt: ImagePrompt) -> ImageGenerationRequest:
    return ImageGenerationRequest(
        prompt=prompt.prompt,
        negative_prompt=prompt.negative_prompt,
        aspect_ratio=prompt.aspect_ratio,
        seed=prompt.seed,
        style=prompt.style,
    )


async def _generate_all(
    provider: ImageProvider, prompts: list[ImagePrompt]
) -> list[ImageGenerationResponse]:
    responses: list[ImageGenerationResponse] = []
    with Progress(console=_console) as progress:
        task = progress.add_task("Generating images", total=len(prompts))
        for prompt in prompts:
            responses.append(await provider.generate(_to_request(prompt)))
            progress.advance(task)
    return responses


def image_command(
    input_path: Annotated[
        Path, typer.Option("--input", help="Path to an image_prompts JSON file.")
    ],
) -> None:
    """Generate every image from an image-prompts file with the configured provider."""
    settings = load_settings()
    storage = ImageStorage(settings.app.output_dir / "images")
    try:
        prompts = read_image_prompts(input_path)
        provider = ImageProviderFactory.create(settings, storage)
        responses = asyncio.run(_generate_all(provider, prompts))
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    render_image_summary(responses)
    _console.print(f"[green]Saved[/green] {len(responses)} images to {storage.directory}")
