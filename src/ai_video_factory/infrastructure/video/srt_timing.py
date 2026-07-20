"""Parse subtitle (``.srt``) cue timings for video composition (pure, no I/O).

Only the timings and count are needed here — the subtitle *text* is burned into
the video directly from the ``.srt`` file by the ffmpeg ``subtitles`` filter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_TIMING_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)


@dataclass(frozen=True)
class SrtCue:
    """A subtitle cue's timing (seconds), 1-based index."""

    index: int
    start: float
    end: float


def _to_seconds(hours: str, minutes: str, seconds: str, millis: str) -> float:
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis.ljust(3, "0")) / 1000


def parse_srt_cues(text: str) -> list[SrtCue]:
    """Return the ordered timed cues found in SubRip ``text``."""
    cues: list[SrtCue] = []
    for match in _TIMING_RE.finditer(text):
        start = _to_seconds(*match.group(1, 2, 3, 4))
        end = _to_seconds(*match.group(5, 6, 7, 8))
        cues.append(SrtCue(index=len(cues) + 1, start=start, end=max(end, start)))
    return cues
