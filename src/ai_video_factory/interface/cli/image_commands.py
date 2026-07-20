"""``ai-video-factory image`` CLI command (interface layer).

Reads image prompts, generates every image with the configured provider
(showing a Rich progress bar), and saves them under ``output/images/``.
All generation logic lives in the infrastructure image provider layer.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress

from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.errors import AppError
from ai_video_factory.infrastructure.config.settings import ImageProviderSettings, load_settings
from ai_video_factory.infrastructure.media.image_dimensions import read_image_dimensions
from ai_video_factory.infrastructure.media.image_storage import ImageStorage
from ai_video_factory.infrastructure.providers.image.base.models import ImageGenerationRequest
from ai_video_factory.infrastructure.providers.image.base.provider import ImageProvider
from ai_video_factory.infrastructure.providers.image.base.writer import (
    ImageManifestEntry,
    write_images_manifest,
)
from ai_video_factory.infrastructure.providers.image.factory.image_provider_factory import (
    ImageProviderFactory,
)
from ai_video_factory.infrastructure.story.reader import read_image_prompts
from ai_video_factory.interface.presenters.image_presenter import render_image_run_summary

_console = Console()
_logger = logging.getLogger(__name__)


def _announce_rate_limit(message: str) -> None:
    """Show a rate-limit wait notice (e.g. ``Rate limit reached, waiting 20 seconds...``)."""
    _console.print(f"[yellow]{message}[/yellow]")


def _to_request(prompt: ImagePrompt) -> ImageGenerationRequest:
    return ImageGenerationRequest(
        prompt=prompt.prompt,
        negative_prompt=prompt.negative_prompt,
        aspect_ratio=prompt.aspect_ratio,
        seed=prompt.seed,
        style=prompt.style,
    )


def _target_for(images_dir: Path, index: int) -> Path:
    return images_dir / f"{index:03d}.png"


async def _generate_images(
    provider: ImageProvider,
    prompts: list[ImagePrompt],
    images_dir: Path,
    *,
    force: bool,
    on_progress: Callable[[], None],
) -> tuple[int, int, int]:
    """Generate every prompt, skipping existing files and continuing on failure.

    The provider saves each image (auto-numbered) into a work directory; it is
    then moved to the index-aligned ``NNN.png``. Returns
    ``(generated, skipped, failed)``.
    """
    generated = skipped = failed = 0
    for index, prompt in enumerate(prompts, start=1):
        target = _target_for(images_dir, index)
        if target.exists() and not force:
            skipped += 1
            on_progress()
            continue
        try:
            response = await provider.generate(_to_request(prompt))
            response.image_path.replace(target)  # atomic same-filesystem rename
            generated += 1
        except AppError as exc:
            failed += 1
            _logger.warning("image %03d failed after retries: %s", index, exc)
        on_progress()
    return generated, skipped, failed


def _manifest_entries(
    prompts: list[ImagePrompt], images_dir: Path, image_settings: ImageProviderSettings
) -> list[ImageManifestEntry]:
    """Build a manifest entry for every prompt whose image file now exists."""
    entries: list[ImageManifestEntry] = []
    for index, prompt in enumerate(prompts, start=1):
        target = _target_for(images_dir, index)
        if not target.exists():
            continue
        width, height = read_image_dimensions(target.read_bytes()) or (0, 0)
        created_at = datetime.fromtimestamp(target.stat().st_mtime, tz=UTC).isoformat()
        entries.append(
            ImageManifestEntry(
                index=index,
                filename=target.name,
                prompt=prompt.prompt,
                provider=image_settings.provider,
                model=image_settings.model,
                width=width,
                height=height,
                created_at=created_at,
            )
        )
    return entries


def image_command(
    input_path: Annotated[
        Path, typer.Option("--input", help="Path to an image_prompts JSON file.")
    ],
    force: Annotated[
        bool, typer.Option("--force", help="Regenerate even if images already exist.")
    ] = False,
) -> None:
    """Generate every image from an image-prompts file with the configured provider."""
    settings = load_settings()
    images_dir = settings.app.output_dir / "images"
    try:
        prompts = read_image_prompts(input_path)
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not prompts:
        _console.print("[yellow]No image prompts to generate.[/yellow]")
        return

    images_dir.mkdir(parents=True, exist_ok=True)
    work_dir = images_dir / ".work"
    storage = ImageStorage(work_dir, prefix="")
    try:
        provider = ImageProviderFactory.create(
            settings, storage, on_rate_limit=_announce_rate_limit
        )
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    try:
        with Progress(console=_console) as progress:
            task = progress.add_task("Generating images", total=len(prompts))
            generated, skipped, failed = asyncio.run(
                _generate_images(
                    provider,
                    prompts,
                    images_dir,
                    force=force,
                    on_progress=lambda: progress.advance(task),
                )
            )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    write_images_manifest(
        images_dir / "manifest.json",
        _manifest_entries(prompts, images_dir, settings.image_provider),
    )
    render_image_run_summary(generated=generated, skipped=skipped, failed=failed)
    _console.print(
        f"[green]Done.[/green] {generated} generated, {skipped} skipped, "
        f"{failed} failed in {images_dir}"
    )


def image_models_command() -> None:
    """List every image model returned by the provider, marking the configured one."""
    settings = load_settings()
    configured = settings.image_provider.model
    storage = ImageStorage(settings.app.output_dir / "images")
    try:
        provider = ImageProviderFactory.create(settings, storage)
        models = asyncio.run(provider.models())
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not models:
        _console.print("[yellow]No models returned by the provider.[/yellow]")
        return
    for name in models:
        if name.removeprefix("models/") == configured or name == configured:
            _console.print(f"[green]* {name}  (configured)[/green]")
        else:
            _console.print(f"  {name}")
    _console.print(f"\nConfigured image model: [cyan]{configured}[/cyan]")
