"""Tests for grouping storyboard shots into 4-8 second clips."""

from __future__ import annotations

from ai_video_factory.domain.value_objects.storyboard import Storyboard, StoryboardShot
from ai_video_factory.infrastructure.video.providers.clip_planner import (
    MAX_CLIP_SECONDS,
    MIN_CLIP_SECONDS,
    plan_clips,
)


def _storyboard(*scene_durations: tuple[int, list[int]]) -> Storyboard:
    """Build a storyboard from ``(scene_id, [shot durations])`` pairs."""
    shots: list[StoryboardShot] = []
    elapsed = 0.0
    for scene_id, durations in scene_durations:
        for order, duration in enumerate(durations, start=1):
            shots.append(
                StoryboardShot(
                    id=len(shots) + 1,
                    scene_id=scene_id,
                    order=order,
                    duration=duration,
                    speech_start=elapsed,
                    speech_end=elapsed + duration,
                    video_prompt=f"prompt {len(shots) + 1}",
                    subtitle=f"line {len(shots) + 1}",
                    image_prompt=f"still {len(shots) + 1}",
                )
            )
            elapsed += duration
    return Storyboard(title="t", total_duration=elapsed, shots=tuple(shots))


def test_short_shots_are_merged_into_the_clip_band() -> None:
    """Three-second shots cannot be rendered alone; two make a 6s clip."""
    clips = plan_clips(_storyboard((1, [3, 3, 3, 3])))

    assert [clip.duration for clip in clips] == [6, 6]
    assert [clip.shot_ids for clip in clips] == [(1, 2), (3, 4)]


def test_every_clip_lands_in_the_band_when_the_scene_allows() -> None:
    clips = plan_clips(_storyboard((1, [3, 3, 3, 3, 3, 3])))

    assert all(MIN_CLIP_SECONDS <= clip.duration <= MAX_CLIP_SECONDS for clip in clips)


def test_a_clip_never_exceeds_the_ceiling() -> None:
    clips = plan_clips(_storyboard((1, [5, 5, 5, 5])))

    assert all(clip.duration <= MAX_CLIP_SECONDS for clip in clips)
    assert [clip.duration for clip in clips] == [5, 5, 5, 5]


def test_the_timeline_is_preserved_exactly() -> None:
    """Merging must not drop, stretch or reorder a single second."""
    storyboard = _storyboard((1, [3, 3, 3]), (2, [4, 2, 5]))

    clips = plan_clips(storyboard)

    assert sum(clip.duration for clip in clips) == storyboard.total_duration
    covered = [shot_id for clip in clips for shot_id in clip.shot_ids]
    assert covered == [shot.id for shot in storyboard.shots]


def test_clips_never_cross_a_scene_boundary() -> None:
    """A scene change is a hard cut; one clip cannot span two places."""
    clips = plan_clips(_storyboard((1, [3]), (2, [3]), (3, [3])))

    assert [clip.scene_id for clip in clips] == [1, 2, 3]
    assert all(len(clip.shot_ids) == 1 for clip in clips)


def test_a_scene_too_short_for_the_floor_yields_one_short_clip() -> None:
    """Better a 3s clip than a cut across two unrelated scenes."""
    clips = plan_clips(_storyboard((1, [3]), (2, [6])))

    assert clips[0].duration == 3
    assert clips[0].is_short
    assert not clips[1].is_short


def test_clip_ids_are_sequential_across_the_whole_storyboard() -> None:
    clips = plan_clips(_storyboard((1, [3, 3]), (2, [3, 3])))

    assert [clip.clip_id for clip in clips] == [1, 2]


def test_a_clip_spans_from_its_first_shot_to_its_last() -> None:
    clips = plan_clips(_storyboard((1, [3, 3, 3, 3])))

    assert (clips[0].start, clips[0].end) == (0.0, 6.0)
    assert (clips[1].start, clips[1].end) == (6.0, 12.0)


def test_merged_clips_carry_the_text_of_every_shot_they_cover() -> None:
    clips = plan_clips(_storyboard((1, [3, 3])))

    assert "prompt 1" in clips[0].prompt
    assert "prompt 2" in clips[0].prompt
    assert "line 1" in clips[0].subtitle
    assert "line 2" in clips[0].subtitle


def test_a_merged_clip_takes_the_opening_shots_still() -> None:
    clips = plan_clips(_storyboard((1, [3, 3])))

    assert clips[0].image_prompt == "still 1"


def test_repeated_text_is_not_duplicated() -> None:
    """Adjacent shots often share a subtitle; saying it twice helps nobody."""
    storyboard = _storyboard((1, [3, 3]))
    shots = tuple(shot.model_copy(update={"subtitle": "same line"}) for shot in storyboard.shots)

    clips = plan_clips(storyboard.model_copy(update={"shots": shots}))

    assert clips[0].subtitle == "same line"


def test_an_empty_storyboard_plans_nothing() -> None:
    assert plan_clips(Storyboard(title="t")) == []


def test_a_long_scene_splits_into_several_clips() -> None:
    clips = plan_clips(_storyboard((1, [3] * 10)))

    assert len(clips) == 5
    assert all(clip.scene_id == 1 for clip in clips)
    assert sum(clip.duration for clip in clips) == 30
