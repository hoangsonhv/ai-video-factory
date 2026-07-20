"""Tests for ffmpeg command generation (pure — no ffmpeg invoked)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_video_factory.infrastructure.config.settings import VideoSettings
from ai_video_factory.infrastructure.video.ffmpeg_command import (
    FfmpegClip,
    build_ffmpeg_command,
    escape_subtitle_path,
)


def _clips(n: int) -> list[FfmpegClip]:
    return [FfmpegClip(image_path=Path(f"img/{i:03d}.png"), duration=2.0) for i in range(1, n + 1)]


def _command(clips: list[FfmpegClip]) -> list[str]:
    return build_ffmpeg_command(
        clips=clips,
        audio_path=Path("audio/narration.mp3"),
        subtitle_path=Path("subs/narration.srt"),
        output_path=Path("out/final.mp4"),
        settings=VideoSettings(),
    )


def test_command_has_encoding_and_resolution_settings() -> None:
    command = _command(_clips(2))
    joined = " ".join(command)

    assert command[0] == "ffmpeg"
    assert "-y" in command
    assert "libx264" in command
    assert "aac" in command
    assert "-r" in command and "30" in command
    assert "-pix_fmt" in command and "yuv420p" in command
    assert "scale=1080:1920" in joined
    assert command[-1] == str(Path("out/final.mp4"))


def test_one_looped_input_per_clip_plus_audio() -> None:
    clips = _clips(3)
    command = _command(clips)

    assert command.count("-loop") == 3  # one per image
    assert command.count("-i") == 4  # three images + one audio
    # audio is the last input, mapped by its index
    assert command[command.index("-map") + 3] == "3:a"


def test_ken_burns_and_subtitles_are_present() -> None:
    joined = " ".join(_command(_clips(2)))
    assert "zoompan=" in joined  # Ken Burns slow zoom
    assert "subtitles=" in joined  # burned-in subtitles


def test_crossfade_between_multiple_images() -> None:
    joined = " ".join(_command(_clips(3)))
    assert "xfade=transition=fade" in joined
    # two transitions for three clips
    assert joined.count("xfade=transition=fade") == 2


def test_single_image_has_no_crossfade() -> None:
    joined = " ".join(_command(_clips(1)))
    assert "xfade" not in joined
    assert "subtitles=" in joined  # still burns subtitles


def test_crossfade_offsets_are_cumulative() -> None:
    # clips of 2.0s display + 0.5s fade padding -> length 2.5 each.
    clips = _clips(3)
    joined = " ".join(_command(clips))
    # first fade begins at length0 - fade = 2.5 - 0.5 = 2.000
    assert "offset=2.000" in joined
    # second at (2.0 + 2.5) - 0.5 = 4.000
    assert "offset=4.000" in joined


def test_reuse_last_image_reflected_in_inputs() -> None:
    # Caller expands clips (reuse-last) before building; verify identical paths pass through.
    same = Path("img/001.png")
    clips = [FfmpegClip(image_path=same, duration=2.0) for _ in range(3)]
    command = build_ffmpeg_command(
        clips=clips,
        audio_path=Path("a.mp3"),
        subtitle_path=Path("s.srt"),
        output_path=Path("o.mp4"),
        settings=VideoSettings(),
    )
    assert command.count(str(same)) == 3


def test_empty_clips_raises() -> None:
    with pytest.raises(ValueError, match="at least one clip"):
        build_ffmpeg_command(
            clips=[],
            audio_path=Path("a.mp3"),
            subtitle_path=Path("s.srt"),
            output_path=Path("o.mp4"),
            settings=VideoSettings(),
        )


def test_subtitle_path_is_escaped_for_windows() -> None:
    escaped = escape_subtitle_path(Path("C:\\Users\\x\\narration.srt"))
    assert escaped == "'C\\:/Users/x/narration.srt'"


def test_custom_settings_flow_through() -> None:
    settings = VideoSettings(width=720, height=1280, fps=24, video_codec="libx265")
    joined = " ".join(
        build_ffmpeg_command(
            clips=_clips(1),
            audio_path=Path("a.mp3"),
            subtitle_path=Path("s.srt"),
            output_path=Path("o.mp4"),
            settings=settings,
        )
    )
    assert "scale=720:1280" in joined
    assert "libx265" in joined
