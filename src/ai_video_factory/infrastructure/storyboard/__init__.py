"""Storyboard stage (infrastructure).

Flattens a directed movie onto a timeline: every shot in order with its
absolute position, the narration spoken over it, and the prompts to render it.
Deterministic and offline — no provider call, no compose change.

Pipeline position: Directed Movie -> **Storyboard**
(``movie_directed.json`` -> ``storyboard.json``).
"""

from ai_video_factory.infrastructure.storyboard.builder import (
    build_image_prompt,
    build_storyboard,
    subtitle_for,
)
from ai_video_factory.infrastructure.storyboard.errors import StoryboardError
from ai_video_factory.infrastructure.storyboard.narration import (
    NarrationCue,
    narration_span,
    parse_narration,
    read_audio_duration,
    read_narration,
)
from ai_video_factory.infrastructure.storyboard.reader import (
    read_directed_movie,
    read_optional_library,
    write_storyboard_json,
)

__all__ = [
    "NarrationCue",
    "StoryboardError",
    "build_image_prompt",
    "build_storyboard",
    "narration_span",
    "parse_narration",
    "read_audio_duration",
    "read_directed_movie",
    "read_narration",
    "read_optional_library",
    "subtitle_for",
    "write_storyboard_json",
]
