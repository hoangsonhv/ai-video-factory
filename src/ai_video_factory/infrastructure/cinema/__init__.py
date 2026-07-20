"""Cinematic director stage (infrastructure).

Decides what each scene is for and how each shot is filmed — size, angle, lens,
composition, blocking, light and action — then rebuilds every image prompt from
those decisions.

Deterministic and offline: no provider is contacted, and no video or compose
stage is touched.
"""

from ai_video_factory.infrastructure.cinema.engine import CinemaResult, CinematicDirector
from ai_video_factory.infrastructure.cinema.errors import CinemaError
from ai_video_factory.infrastructure.cinema.scene_director import (
    SceneDirector,
    infer_conflict,
    story_beat,
)
from ai_video_factory.infrastructure.cinema.shot_director import ShotDirector
from ai_video_factory.infrastructure.cinema.vocabulary import (
    ACTIVE_VERBS,
    activate,
    choose_angle,
    choose_composition,
    choose_lens,
    choose_lighting,
    choose_shot_type,
    is_static,
)

__all__ = [
    "ACTIVE_VERBS",
    "CinemaError",
    "CinemaResult",
    "CinematicDirector",
    "SceneDirector",
    "ShotDirector",
    "activate",
    "choose_angle",
    "choose_composition",
    "choose_lens",
    "choose_lighting",
    "choose_shot_type",
    "infer_conflict",
    "is_static",
    "story_beat",
]
