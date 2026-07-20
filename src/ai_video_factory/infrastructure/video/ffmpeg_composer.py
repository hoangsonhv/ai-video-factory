"""``FfmpegVideoComposer`` — the ffmpeg-backed VideoComposer implementation.

Satisfies the existing ``VideoComposer`` protocol (asset pipeline): given the
image directory, narration audio, and subtitle ``.srt`` (as ``AssetResult``s),
it maps one image per subtitle cue (reusing the last image when there are fewer
images than cues), builds the ffmpeg command, and runs it off the event loop
with a single retry. Missing ffmpeg or a persistent failure raises ``MediaError``.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

from ai_video_factory.errors import MediaError
from ai_video_factory.infrastructure.asset_pipeline.models import AssetResult
from ai_video_factory.infrastructure.config.settings import VideoSettings
from ai_video_factory.infrastructure.video.ffmpeg_command import FfmpegClip, build_ffmpeg_command
from ai_video_factory.infrastructure.video.srt_timing import SrtCue, parse_srt_cues

_logger = logging.getLogger(__name__)

# Floor on a single image's on-screen time so a very short cue still animates.
_MIN_CLIP_SECONDS = 0.5

# Runs an ffmpeg argv and returns (return_code, stderr).
FfmpegRunner = Callable[[list[str]], "tuple[int, str]"]


def default_ffmpeg_runner(command: list[str]) -> tuple[int, str]:
    """Run ffmpeg as a blocking subprocess; translate a missing binary."""
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise MediaError(
            f"ffmpeg executable not found: {command[0]!r}. Install FFmpeg and ensure it is on PATH."
        ) from exc
    return completed.returncode, completed.stderr


class FfmpegVideoComposer:
    """Composes the final MP4 from images, narration audio, and subtitles."""

    def __init__(
        self,
        settings: VideoSettings,
        output_path: Path,
        *,
        runner: FfmpegRunner = default_ffmpeg_runner,
    ) -> None:
        self._settings = settings
        self._output_path = output_path
        self._runner = runner

    async def compose_video(
        self, images: AssetResult, voice: AssetResult, subtitles: AssetResult
    ) -> AssetResult:
        images_dir, audio_path, subtitle_path = images.path, voice.path, subtitles.path
        if images_dir is None or audio_path is None or subtitle_path is None:
            raise MediaError("compose_video requires image directory, audio, and subtitle paths")

        image_files = sorted(images_dir.glob("*.png"))
        if not image_files:
            raise MediaError(f"no images found in {images_dir}")
        cues = parse_srt_cues(subtitle_path.read_text(encoding="utf-8"))
        if not cues:
            raise MediaError(f"no subtitle cues found in {subtitle_path}")

        clips = self._build_clips(image_files, cues)
        command = build_ffmpeg_command(
            clips=clips,
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            output_path=self._output_path,
            settings=self._settings,
        )
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        await self._run_with_retry(command)

        return AssetResult(
            success=True,
            path=self._output_path,
            duration=cues[-1].end,
            metadata={
                "fps": self._settings.fps,
                "resolution": f"{self._settings.width}x{self._settings.height}",
                "image_count": len(image_files),
                "subtitle_count": len(cues),
            },
        )

    def _build_clips(self, image_files: list[Path], cues: list[SrtCue]) -> list[FfmpegClip]:
        """One clip per cue; reuse the last image when images < cues (requirement 7)."""
        clips: list[FfmpegClip] = []
        for index, cue in enumerate(cues):
            image = image_files[min(index, len(image_files) - 1)]
            duration = max(cue.end - cue.start, _MIN_CLIP_SECONDS)
            clips.append(FfmpegClip(image_path=image, duration=duration))
        return clips

    async def _run_with_retry(self, command: list[str]) -> None:
        attempts = self._settings.retry_count + 1  # retry_count=1 -> one retry (two attempts)
        return_code = 0
        stderr = ""
        for attempt in range(1, attempts + 1):
            return_code, stderr = await asyncio.to_thread(self._runner, command)
            if return_code == 0:
                return
            _logger.warning("ffmpeg attempt %d/%d failed (code %d)", attempt, attempts, return_code)
        raise MediaError(
            f"ffmpeg failed after {attempts} attempt(s) (exit {return_code})",
            context={"stderr": stderr[-1500:]},
        )
