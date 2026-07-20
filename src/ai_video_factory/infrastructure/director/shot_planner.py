"""Shot-count and duration arithmetic (pure, no I/O).

The sprint's two rules — 3-8 shots per scene, 2-5 seconds per shot — conflict
for short scenes: three shots of at least two seconds need a six-second scene,
so a five-second scene can hold at most two. :func:`target_shot_count` resolves
that by preferring the 3-8 band but never asking for more shots than the scene
can physically hold. The prompt states the target; the parser enforces the
bounds on whatever comes back.
"""

from __future__ import annotations

from ai_video_factory.domain.value_objects.director import MAX_SHOT_SECONDS, MIN_SHOT_SECONDS

MIN_SHOTS = 3
MAX_SHOTS = 8
PREFERRED_SHOT_SECONDS = 3
"""Aim for ~3s shots, then clamp into the 3-8 band the scene can support."""


def max_feasible_shots(duration: int) -> int:
    """How many shots of at least ``MIN_SHOT_SECONDS`` fit in ``duration``."""
    return max(1, duration // MIN_SHOT_SECONDS)


def target_shot_count(duration: int) -> int:
    """How many shots to ask for in a scene of ``duration`` seconds.

    Prefers roughly three-second shots inside the 3-8 band, but never exceeds
    what the scene's length allows — a 5s scene gets 2 shots, not 3.
    """
    ideal = round(duration / PREFERRED_SHOT_SECONDS)
    wanted = max(MIN_SHOTS, ideal)
    return max(1, min(MAX_SHOTS, max_feasible_shots(duration), wanted))


def clamp_shot_duration(duration: int) -> int:
    """Force a shot length into the permitted 2-5 second range."""
    return max(MIN_SHOT_SECONDS, min(MAX_SHOT_SECONDS, duration))


def split_evenly(duration: int, shots: int) -> list[int]:
    """Split ``duration`` across ``shots`` clamped shot lengths.

    Used when the model gives a shot no usable duration: the scene's own length
    is a better guess than an invented number.
    """
    if shots <= 0:
        return []
    base = clamp_shot_duration(round(duration / shots))
    return [base] * shots
