"""AI Director stage (infrastructure).

Breaks a movie's scenes into **shots** — the unit an AI video model renders —
with camera, motion and lighting per shot, plus a composed ``video_prompt``.
Additive: the Movie Builder, Character Library, video providers, image
generation and compose are all untouched.

Pipeline position: Movie → **Director** → Directed Movie
(``movie_consistent.json`` → ``movie_directed.json``). One provider request
plans the whole movie.
"""

from ai_video_factory.infrastructure.director.errors import DirectorError
from ai_video_factory.infrastructure.director.prompt_builder import build_shot_prompt
from ai_video_factory.infrastructure.director.reader import (
    read_movie,
    read_optional_directed_movie,
    read_optional_library,
    write_directed_movie_json,
)
from ai_video_factory.infrastructure.director.report import DirectionReport
from ai_video_factory.infrastructure.director.service import DirectorService
from ai_video_factory.infrastructure.director.shot_parser import parse_scene_shots, parse_shot_plan
from ai_video_factory.infrastructure.director.shot_planner import (
    MAX_SHOTS,
    MIN_SHOTS,
    target_shot_count,
)

__all__ = [
    "MAX_SHOTS",
    "MIN_SHOTS",
    "DirectionReport",
    "DirectorError",
    "DirectorService",
    "build_shot_prompt",
    "parse_scene_shots",
    "parse_shot_plan",
    "read_movie",
    "read_optional_directed_movie",
    "read_optional_library",
    "target_shot_count",
    "write_directed_movie_json",
]
