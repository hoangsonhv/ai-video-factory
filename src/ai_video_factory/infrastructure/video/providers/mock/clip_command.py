"""Build the ffmpeg argv for one mock scene clip (pure, no I/O).

Reuses the project's existing ffmpeg approach — same binary, resolution, fps
and codecs as the final composer (``VideoSettings``) — so a mock clip is a real,
playable MP4 that the compose stage could consume. Two sources are supported:

- a reference image, scaled and cropped to fill the frame, held for the scene's
  duration (the current slideshow behaviour), or
- a flat colour card, when the scene has no reference image yet.

Keeping this a pure function makes command generation unit-testable without
ever invoking ffmpeg.
"""

from __future__ import annotations

from pathlib import Path

from ai_video_factory.infrastructure.config.settings import VideoSettings

PLACEHOLDER_COLOR = "black"


def _fmt(seconds: float) -> str:
    return f"{seconds:.3f}"


def build_clip_command(
    *,
    output_path: Path,
    duration: float,
    settings: VideoSettings,
    reference_image: Path | None = None,
) -> list[str]:
    """Return the ffmpeg argv rendering a single silent clip.

    Raises:
        ValueError: If ``duration`` is not positive.
    """
    if duration <= 0:
        raise ValueError("clip duration must be positive")

    command: list[str] = [settings.ffmpeg_path, "-y"]
    if reference_image is not None:
        command += ["-loop", "1", "-t", _fmt(duration), "-i", str(reference_image)]
        video_filter = (
            f"scale={settings.width}:{settings.height}:force_original_aspect_ratio=increase,"
            f"crop={settings.width}:{settings.height},setsar=1,format=yuv420p"
        )
    else:
        source = f"color=c={PLACEHOLDER_COLOR}:s={settings.width}x{settings.height}"
        command += ["-f", "lavfi", "-t", _fmt(duration), "-i", f"{source}:r={settings.fps}"]
        video_filter = "format=yuv420p"

    command += [
        "-vf",
        video_filter,
        "-c:v",
        settings.video_codec,
        "-r",
        str(settings.fps),
        "-t",
        _fmt(duration),
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    return command
