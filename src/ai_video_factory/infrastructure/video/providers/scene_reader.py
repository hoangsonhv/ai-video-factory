"""Read the scenes to render from a movie JSON file.

Accepts either ``movie.json`` or the consistency-corrected
``movie_consistent.json`` — both are ``Movie`` documents — and turns each scene
into a vendor-neutral :class:`VideoGenerationRequest`.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from pydantic import ValidationError

from ai_video_factory.domain.value_objects.movie import Movie
from ai_video_factory.infrastructure.config.settings import VideoSettings
from ai_video_factory.infrastructure.video.providers.base.models import VideoGenerationRequest
from ai_video_factory.infrastructure.video.providers.errors import VideoProviderError


def read_scene_movie(path: Path) -> Movie:
    """Load a :class:`Movie` from a saved movie JSON file.

    Raises:
        VideoProviderError: If the file is missing, malformed, or invalid.
    """
    if not path.is_file():
        raise VideoProviderError(f"scene file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VideoProviderError(f"invalid JSON in {path}", context={"error": str(exc)}) from exc
    try:
        return Movie.model_validate(data)
    except ValidationError as exc:
        raise VideoProviderError(
            "scene file does not match the movie schema", context={"error": str(exc)}
        ) from exc


def aspect_ratio(settings: VideoSettings) -> str:
    """The configured frame as a reduced ratio (1080x1920 → ``9:16``)."""
    divisor = math.gcd(settings.width, settings.height)
    return f"{settings.width // divisor}:{settings.height // divisor}"


def scene_images(images_dir: Path | None, position: int) -> tuple[Path, ...]:
    """The reference image for the scene at 1-based ``position``, if present.

    Images are produced as ``001.png``, ``002.png``, … in scene order, so a
    scene is matched by position rather than by ``scene.id``. A missing file
    yields no reference — image-to-video providers then fail that scene with a
    clear message, while the local mock falls back to a colour card.
    """
    if images_dir is None:
        return ()
    candidate = images_dir / f"{position:03d}.png"
    return (candidate,) if candidate.is_file() else ()


def build_requests(
    movie: Movie, settings: VideoSettings, *, images_dir: Path | None = None
) -> list[VideoGenerationRequest]:
    """Turn every scene of ``movie`` into a video-generation request.

    ``images_dir`` attaches each scene's generated image as its reference
    image; omitted, requests carry none (the Sprint 020 behaviour).

    Raises:
        VideoProviderError: If the movie declares no scenes.
    """
    if not movie.scenes:
        raise VideoProviderError("movie declares no scenes to render")
    ratio = aspect_ratio(settings)
    return [
        VideoGenerationRequest(
            scene_id=scene.id,
            # One clip per scene on this legacy route, numbered by position so
            # each lands in its own file.
            clip_id=position,
            prompt=scene.video_prompt or scene.image_prompt,
            duration=float(scene.duration),
            aspect_ratio=ratio,
            fps=settings.fps,
            reference_images=scene_images(images_dir, position),
            camera=scene.camera,
            style=movie.style,
        )
        for position, scene in enumerate(movie.scenes, start=1)
    ]
