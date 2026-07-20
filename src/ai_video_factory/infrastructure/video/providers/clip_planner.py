"""Group storyboard shots into renderable clips (pure, no I/O).

AI video providers render in a band of a few seconds — shorter than a shot,
longer than the storyboard's 2-5s units. This module merges **consecutive
shots within one scene** until each clip lands in the 4-8s band, so the
timeline is preserved exactly: no shot is dropped, stretched or reordered, and
the clips still sum to the storyboard's total running time.

Scene boundaries are never crossed. A scene change is a hard cut, and a single
clip spanning one would ask the provider to render two unrelated places at
once. A scene too short to reach the minimum yields one short clip, reported
rather than padded.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from ai_video_factory.domain.value_objects.storyboard import Storyboard, StoryboardShot

MIN_CLIP_SECONDS = 4
MAX_CLIP_SECONDS = 8
"""The band a clip must land in; scene boundaries take precedence over both."""


class ClipPlan(BaseModel):
    """One clip: the consecutive shots it covers and where it sits."""

    model_config = ConfigDict(frozen=True)

    clip_id: int = Field(ge=1)
    scene_id: int = Field(ge=1)
    shot_ids: tuple[int, ...] = ()
    duration: int = Field(gt=0)
    start: float = Field(default=0.0, ge=0.0)
    end: float = Field(default=0.0, ge=0.0)
    prompt: str = ""
    subtitle: str = ""
    image_prompt: str = ""

    @property
    def is_short(self) -> bool:
        """Whether the clip falls below the provider-friendly minimum.

        Only happens when a whole scene is shorter than ``MIN_CLIP_SECONDS``;
        the alternative would be crossing a scene cut.
        """
        return self.duration < MIN_CLIP_SECONDS


def _group_scene(shots: Sequence[StoryboardShot]) -> list[list[StoryboardShot]]:
    """Split one scene's shots into runs that each land in the clip band."""
    groups: list[list[StoryboardShot]] = []
    current: list[StoryboardShot] = []
    total = 0

    for shot in shots:
        # Close the current run when adding this shot would overshoot the
        # ceiling, provided the run already satisfies the floor.
        if current and total + shot.duration > MAX_CLIP_SECONDS and total >= MIN_CLIP_SECONDS:
            groups.append(current)
            current, total = [], 0
        current.append(shot)
        total += shot.duration
        if total >= MAX_CLIP_SECONDS:
            groups.append(current)
            current, total = [], 0

    if current:
        groups.append(current)
    return groups


def _merge_text(values: Sequence[str]) -> str:
    """Join distinct, non-empty fragments in order."""
    seen: set[str] = set()
    merged: list[str] = []
    for value in values:
        cleaned = " ".join(value.split()).strip()
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            merged.append(cleaned)
    return " ".join(merged)


def plan_clips(storyboard: Storyboard) -> list[ClipPlan]:
    """Group ``storyboard``'s shots into clips of 4-8 seconds.

    Shots are taken in timeline order; consecutive shots from the same scene
    are merged until the clip reaches the band. The clips' durations sum to the
    storyboard's total, so the timeline is preserved.
    """
    by_scene: list[tuple[int, list[StoryboardShot]]] = []
    for shot in storyboard.shots:
        if by_scene and by_scene[-1][0] == shot.scene_id:
            by_scene[-1][1].append(shot)
        else:
            by_scene.append((shot.scene_id, [shot]))

    clips: list[ClipPlan] = []
    for scene_id, shots in by_scene:
        for group in _group_scene(shots):
            clips.append(
                ClipPlan(
                    clip_id=len(clips) + 1,
                    scene_id=scene_id,
                    shot_ids=tuple(shot.id for shot in group),
                    duration=sum(shot.duration for shot in group),
                    start=group[0].speech_start,
                    end=group[-1].speech_end,
                    prompt=_merge_text([shot.video_prompt for shot in group]),
                    subtitle=_merge_text([shot.subtitle for shot in group]),
                    image_prompt=group[0].image_prompt,
                )
            )
    return clips
