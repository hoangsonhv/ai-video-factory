"""Read the narration's timed cues, text included (pure parsing, no vendor code).

The compose stage already parses ``.srt`` timings, but deliberately drops the
text — ffmpeg burns subtitles straight from the file. The storyboard needs the
words as well, so it parses its own cues rather than changing that module.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ai_video_factory.infrastructure.storyboard.errors import StoryboardError

_TIMING_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)


class NarrationCue(BaseModel):
    """One subtitle cue: when it plays and what it says."""

    model_config = ConfigDict(frozen=True)

    start: float = Field(ge=0.0)
    end: float = Field(ge=0.0)
    text: str = ""

    def overlaps(self, start: float, end: float) -> bool:
        """Whether this cue sounds at any point within ``[start, end)``."""
        return self.start < end and self.end > start


def _to_seconds(hours: str, minutes: str, seconds: str, millis: str) -> float:
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis.ljust(3, "0")) / 1000


def parse_narration(text: str) -> list[NarrationCue]:
    """Parse SubRip ``text`` into timed cues with their words."""
    cues: list[NarrationCue] = []
    blocks = re.split(r"\n\s*\n", text.strip())
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        match = next((_TIMING_RE.search(line) for line in lines if _TIMING_RE.search(line)), None)
        if match is None:
            continue
        start = _to_seconds(*match.group(1, 2, 3, 4))
        end = _to_seconds(*match.group(5, 6, 7, 8))
        timing_index = next(i for i, line in enumerate(lines) if _TIMING_RE.search(line))
        spoken = " ".join(lines[timing_index + 1 :]).strip()
        cues.append(NarrationCue(start=start, end=max(end, start), text=spoken))
    return cues


def read_narration(path: Path) -> list[NarrationCue]:
    """Load narration cues from a ``.srt`` file, or ``[]`` if it is absent.

    A missing subtitle file is not an error: the storyboard is still built,
    just without spoken text mapped onto the shots.

    Raises:
        StoryboardError: If the file exists but cannot be read.
    """
    if not path.is_file():
        return []
    try:
        return parse_narration(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise StoryboardError(f"cannot read narration {path}: {exc}") from exc


def read_audio_duration(path: Path) -> float:
    """Read the narration length from the TTS metadata beside the audio file.

    Returns ``0.0`` when the metadata is missing or unusable — the storyboard
    then reports no narration duration rather than guessing one.
    """
    if not path.is_file():
        return 0.0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0.0
    duration = payload.get("duration") if isinstance(payload, dict) else None
    return round(float(duration), 3) if isinstance(duration, int | float) else 0.0


def narration_span(cues: list[NarrationCue]) -> float:
    """The end of the last cue, i.e. how long the narration speaks for."""
    return round(max((cue.end for cue in cues), default=0.0), 3)
