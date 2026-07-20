"""Build the ffmpeg argv for composing the final video (pure, no I/O).

The generated command turns one still image per subtitle cue into a portrait
1080x1920 H.264/AAC video with:
- a subtle Ken Burns slow zoom per image (``zoompan``),
- smooth crossfades between images (``xfade``),
- burned-in subtitles read from the ``.srt`` (``subtitles`` filter),
- the narration audio, trimmed to length (``-shortest``).

Keeping this a pure function makes command generation unit-testable without
ever invoking ffmpeg.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_video_factory.infrastructure.config.settings import VideoSettings

# Ken Burns tuning: how fast the zoom creeps in, and its ceiling.
_ZOOM_STEP = 0.0015
_MAX_ZOOM = 1.15


@dataclass(frozen=True)
class FfmpegClip:
    """One image shown for ``duration`` seconds (its subtitle window)."""

    image_path: Path
    duration: float


def _fmt(seconds: float) -> str:
    return f"{seconds:.3f}"


def escape_subtitle_path(path: Path) -> str:
    """Escape a path for ffmpeg's ``subtitles`` filter (Windows-safe)."""
    escaped = str(path).replace("\\", "/").replace(":", "\\:")
    return f"'{escaped}'"


def _ken_burns(index: int, clip_seconds: float, settings: VideoSettings) -> str:
    frames = max(1, round(clip_seconds * settings.fps))
    return (
        f"[{index}:v]scale={settings.width}:{settings.height}:force_original_aspect_ratio=increase,"
        f"crop={settings.width}:{settings.height},"
        f"zoompan=z='min(zoom+{_ZOOM_STEP},{_MAX_ZOOM})':d={frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"s={settings.width}x{settings.height}:fps={settings.fps},"
        f"setsar=1,format=yuv420p[v{index}]"
    )


def build_filter_complex(
    clips: list[FfmpegClip], subtitle_path: Path, settings: VideoSettings
) -> str:
    """Build the ``-filter_complex`` graph string for ``clips``."""
    fade = settings.fade_duration
    # Each clip is padded by ``fade`` so consecutive images have overlap to cross-fade.
    clip_lengths = [clip.duration + fade for clip in clips]
    parts = [_ken_burns(index, clip_lengths[index], settings) for index in range(len(clips))]

    if len(clips) == 1:
        video_label = "v0"
    else:
        previous = "v0"
        previous_length = clip_lengths[0]
        for k in range(1, len(clips)):
            offset = previous_length - fade
            label = f"x{k}"
            parts.append(
                f"[{previous}][v{k}]xfade=transition=fade:"
                f"duration={_fmt(fade)}:offset={_fmt(offset)}[{label}]"
            )
            previous = label
            previous_length = offset + clip_lengths[k]
        video_label = previous

    parts.append(f"[{video_label}]subtitles={escape_subtitle_path(subtitle_path)}[vout]")
    return ";".join(parts)


def build_ffmpeg_command(
    *,
    clips: list[FfmpegClip],
    audio_path: Path,
    subtitle_path: Path,
    output_path: Path,
    settings: VideoSettings,
) -> list[str]:
    """Return the full ffmpeg argv to compose the final video from ``clips``."""
    if not clips:
        raise ValueError("at least one clip is required")

    command: list[str] = [settings.ffmpeg_path, "-y"]
    for clip in clips:
        command += ["-loop", "1", "-t", _fmt(clip.duration + settings.fade_duration)]
        command += ["-i", str(clip.image_path)]
    command += ["-i", str(audio_path)]

    audio_index = len(clips)
    command += ["-filter_complex", build_filter_complex(clips, subtitle_path, settings)]
    command += ["-map", "[vout]", "-map", f"{audio_index}:a"]
    command += [
        "-c:v",
        settings.video_codec,
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(settings.fps),
        "-c:a",
        settings.audio_codec,
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    return command
