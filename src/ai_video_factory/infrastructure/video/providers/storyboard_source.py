"""Turn a storyboard into clip requests and their references (pure, no I/O).

Bridges the storyboard stage to the video providers: shots are grouped into
4-8 second clips (:mod:`.clip_planner`), each clip becomes a vendor-neutral
:class:`VideoGenerationRequest`, and each request is paired with the stills a
provider may condition on to hold consistency across clips.

Reading files is the caller's job — this module only decides *which* paths a
clip should reference, so the whole mapping stays testable without a disk.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import ValidationError

from ai_video_factory.domain.value_objects.character_library import CharacterProfile
from ai_video_factory.domain.value_objects.storyboard import Storyboard
from ai_video_factory.infrastructure.config.settings import VideoSettings
from ai_video_factory.infrastructure.video.providers.base.models import (
    ClipReferences,
    VideoGenerationRequest,
)
from ai_video_factory.infrastructure.video.providers.clip_planner import ClipPlan, plan_clips
from ai_video_factory.infrastructure.video.providers.errors import VideoProviderError


def read_storyboard(path: Path) -> Storyboard:
    """Load a :class:`Storyboard` from ``storyboard.json``.

    Raises:
        VideoProviderError: If the file is missing, malformed, or invalid.
    """
    if not path.is_file():
        raise VideoProviderError(f"storyboard not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VideoProviderError(f"invalid JSON in {path}", context={"error": str(exc)}) from exc
    try:
        return Storyboard.model_validate(data)
    except ValidationError as exc:
        raise VideoProviderError(
            f"{path} does not match the storyboard schema; re-run `storyboard`",
            context={"error": str(exc)},
        ) from exc


def aspect_ratio(settings: VideoSettings) -> str:
    """The configured frame as a reduced ratio (1080x1920 -> ``9:16``)."""
    divisor = math.gcd(settings.width, settings.height)
    return f"{settings.width // divisor}:{settings.height // divisor}"


def scene_image(images_dir: Path | None, scene_id: int) -> Path | None:
    """The generated still for a scene, matched by its 1-based number."""
    if images_dir is None:
        return None
    candidate = images_dir / f"{scene_id:03d}.png"
    return candidate if candidate.is_file() else None


def character_images(profiles: Mapping[str, CharacterProfile], character: str) -> tuple[Path, ...]:
    """The reference stills pinned to the characters named in a clip.

    A character library entry only contributes when it actually carries a
    ``reference_image`` — an absent one is left absent rather than substituted.
    """
    references: list[Path] = []
    for name in character.replace(",", " ").split():
        profile = profiles.get(name.strip().lower())
        if profile is not None and profile.reference_image:
            path = Path(profile.reference_image)
            if path.is_file():
                references.append(path)
    return tuple(dict.fromkeys(references))


def build_references(
    clip: ClipPlan,
    *,
    character: str,
    profiles: Mapping[str, CharacterProfile],
    images_dir: Path | None,
    previous_clip: Path | None,
) -> ClipReferences:
    """Collect the stills a provider may use to keep this clip consistent."""
    return ClipReferences(
        character=character_images(profiles, character),
        scene=scene_image(images_dir, clip.scene_id),
        previous_clip=previous_clip if previous_clip and previous_clip.is_file() else None,
    )


def build_requests(
    storyboard: Storyboard,
    settings: VideoSettings,
    *,
    negative_prompt: str = "",
) -> list[tuple[ClipPlan, VideoGenerationRequest]]:
    """Turn a storyboard into one request per 4-8 second clip.

    Raises:
        VideoProviderError: If the storyboard carries no shots.
    """
    clips = plan_clips(storyboard)
    if not clips:
        raise VideoProviderError("storyboard carries no shots to render")

    ratio = aspect_ratio(settings)
    return [
        (
            clip,
            VideoGenerationRequest(
                scene_id=clip.scene_id,
                clip_id=clip.clip_id,
                shot_ids=clip.shot_ids,
                prompt=clip.prompt,
                negative_prompt=negative_prompt,
                duration=float(clip.duration),
                aspect_ratio=ratio,
                width=settings.width,
                height=settings.height,
                fps=settings.fps,
                style=storyboard.style,
            ),
        )
        for clip in clips
    ]


def shot_character(storyboard: Storyboard, shot_ids: Sequence[int]) -> str:
    """The characters appearing across the shots a clip covers."""
    names: list[str] = []
    for shot in storyboard.shots:
        if shot.id in set(shot_ids) and shot.character:
            names.extend(part.strip() for part in shot.character.replace(",", " ").split())
    return " ".join(dict.fromkeys(name for name in names if name))
