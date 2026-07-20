"""Format timed transcription segments as SubRip (``.srt``) subtitle text.

Pure formatting (no I/O). Segments are renumbered sequentially and timestamps
are rendered as ``HH:MM:SS,mmm``; the text is preserved verbatim (UTF-8),
so Vietnamese diacritics survive.
"""

from __future__ import annotations

from collections.abc import Sequence

from ai_video_factory.infrastructure.providers.transcription.base.models import TranscriptionSegment

_MIN_CUE_SECONDS = 0.001


def _format_timestamp(seconds: float) -> str:
    total_millis = round(max(seconds, 0.0) * 1000)
    hours, total_millis = divmod(total_millis, 3_600_000)
    minutes, total_millis = divmod(total_millis, 60_000)
    secs, millis = divmod(total_millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def to_srt(segments: Sequence[TranscriptionSegment]) -> str:
    """Render ``segments`` as SubRip subtitle text (trailing newline included)."""
    blocks: list[str] = []
    for index, segment in enumerate(segments, start=1):
        end = max(segment.end, segment.start + _MIN_CUE_SECONDS)  # SRT needs end > start
        start_ts = _format_timestamp(segment.start)
        end_ts = _format_timestamp(end)
        blocks.append(f"{index}\n{start_ts} --> {end_ts}\n{segment.text.strip()}\n")
    return "\n".join(blocks)
