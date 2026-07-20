"""Tests for the storyboard builder: timeline, narration mapping, prompts."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ai_video_factory.domain.value_objects.character_library import CharacterProfile
from ai_video_factory.domain.value_objects.director import DirectedMovie, DirectedScene, Shot
from ai_video_factory.domain.value_objects.movie import Location
from ai_video_factory.domain.value_objects.storyboard import Storyboard, StoryboardShot
from ai_video_factory.infrastructure.storyboard.builder import (
    STILL_DIRECTIVE,
    build_storyboard,
    subtitle_for,
)
from ai_video_factory.infrastructure.storyboard.errors import StoryboardError
from ai_video_factory.infrastructure.storyboard.narration import (
    NarrationCue,
    narration_span,
    parse_narration,
)

STORYBOARD_FIELDS = {
    "id",
    "scene_id",
    "order",
    "duration",
    "camera",
    "camera_motion",
    "lens",
    "framing",
    "transition",
    "character",
    "action",
    "expression",
    "environment",
    "lighting",
    "speech_start",
    "speech_end",
    "subtitle",
    "image_prompt",
    "video_prompt",
    "audio_segment",
}


def _shot(shot_id: int = 1, duration: int = 3, **overrides: object) -> Shot:
    defaults: dict[str, object] = {
        "id": shot_id,
        "duration": duration,
        "camera": "medium shot",
        "camera_motion": "slow push in",
        "lens": "50mm",
        "framing": "rule of thirds",
        "subject": "lin_tian",
        "action": "draws a sword",
        "expression": "resolve hardening",
        "environment_motion": "embers drifting",
        "lighting": "hard key",
        "transition": "cut",
        "video_prompt": "a composed video prompt",
    }
    defaults.update(overrides)
    return Shot.model_validate(defaults)


def _movie(*scene_shots: tuple[int, list[Shot]]) -> DirectedMovie:
    pairs = scene_shots or ((1, [_shot(1), _shot(2)]), (2, [_shot(1)]))
    return DirectedMovie(
        title="Tu Tiên",
        style="cinematic",
        duration=60,
        locations=(Location(id="cliff", name="Cliff", description="sunrise over the sea"),),
        scenes=tuple(
            DirectedScene(
                id=scene_id,
                duration=sum(shot.duration for shot in shots) or 5,
                location="cliff",
                characters=("lin_tian",),
                emotion="resolve",
                shots=tuple(shots),
            )
            for scene_id, shots in pairs
        ),
    )


def _profiles() -> dict[str, CharacterProfile]:
    return {
        "lin_tian": CharacterProfile(
            id="lin_tian",
            master_prompt="Lâm Thiên, long black hair, consistent character design",
            negative_prompt="inconsistent face, blurry",
        )
    }


def _cues() -> list[NarrationCue]:
    return [
        NarrationCue(start=0.0, end=2.5, text="Ngày ấy trời rất trong."),
        NarrationCue(start=2.5, end=5.0, text="Anh bước lên vách đá."),
        NarrationCue(start=5.0, end=9.0, text="Thanh kiếm rực sáng."),
    ]


# --- timeline --------------------------------------------------------------


def test_every_shot_becomes_a_storyboard_entry() -> None:
    storyboard = build_storyboard(_movie())

    assert storyboard.shot_count == 3
    assert storyboard.scene_count == 2


def test_shot_ids_run_consecutively_across_the_whole_movie() -> None:
    storyboard = build_storyboard(_movie())

    assert [shot.id for shot in storyboard.shots] == [1, 2, 3]


def test_order_restarts_within_each_scene() -> None:
    storyboard = build_storyboard(_movie())

    assert [(shot.scene_id, shot.order) for shot in storyboard.shots] == [(1, 1), (1, 2), (2, 1)]


def test_shots_are_laid_end_to_end_without_gaps_or_overlap() -> None:
    storyboard = build_storyboard(_movie())

    previous_end = 0.0
    for shot in storyboard.shots:
        assert shot.speech_start == previous_end
        assert shot.speech_end == shot.speech_start + shot.duration
        previous_end = shot.speech_end


def test_the_total_duration_is_the_sum_of_the_shots() -> None:
    storyboard = build_storyboard(_movie())

    assert storyboard.total_duration == sum(shot.duration for shot in storyboard.shots)
    assert storyboard.total_duration == 9.0


def test_shot_durations_are_carried_over_unchanged() -> None:
    """The director owns durations; the storyboard must not rewrite them."""
    movie = _movie((1, [_shot(1, duration=2), _shot(2, duration=5)]))

    storyboard = build_storyboard(movie)

    assert [shot.duration for shot in storyboard.shots] == [2, 5]


def test_every_shot_field_is_carried_from_the_director() -> None:
    storyboard = build_storyboard(_movie())
    shot = storyboard.shots[0]

    assert shot.camera == "medium shot"
    assert shot.camera_motion == "slow push in"
    assert shot.lens == "50mm"
    assert shot.framing == "rule of thirds"
    assert shot.transition == "cut"
    assert shot.character == "lin_tian"
    assert shot.action == "draws a sword"
    assert shot.expression == "resolve hardening"
    assert shot.environment == "embers drifting"
    assert shot.lighting == "hard key"
    assert shot.video_prompt == "a composed video prompt"


def test_the_character_falls_back_to_the_scene_cast() -> None:
    movie = _movie((1, [_shot(1, subject="")]))

    assert build_storyboard(movie).shots[0].character == "lin_tian"


def test_a_movie_without_shots_is_rejected() -> None:
    movie = DirectedMovie(title="x", duration=10, scenes=(DirectedScene(id=1, duration=5),))

    with pytest.raises(StoryboardError, match="run `director`"):
        build_storyboard(movie)


# --- narration mapping -----------------------------------------------------


def test_a_shot_gets_the_narration_spoken_over_it() -> None:
    storyboard = build_storyboard(_movie(), cues=_cues())

    # shot 1 covers 0-3s, so it spans the first cue and part of the second
    assert "Ngày ấy trời rất trong." in storyboard.shots[0].subtitle
    assert "Anh bước lên vách đá." in storyboard.shots[0].subtitle


def test_a_later_shot_gets_only_its_own_narration() -> None:
    storyboard = build_storyboard(_movie(), cues=_cues())

    # shot 3 covers 6-9s: only the third cue is speaking
    assert storyboard.shots[2].subtitle == "Thanh kiếm rực sáng."


def test_subtitle_lookup_uses_overlap_not_containment() -> None:
    cues = [NarrationCue(start=1.0, end=8.0, text="one long sentence")]

    assert subtitle_for(cues, 0.0, 3.0) == "one long sentence"
    assert subtitle_for(cues, 3.0, 6.0) == "one long sentence"
    assert subtitle_for(cues, 9.0, 12.0) == ""


def test_a_cue_ending_exactly_at_a_boundary_does_not_bleed_over() -> None:
    cues = [NarrationCue(start=0.0, end=3.0, text="first")]

    assert subtitle_for(cues, 0.0, 3.0) == "first"
    assert subtitle_for(cues, 3.0, 6.0) == ""


def test_without_narration_shots_carry_no_subtitle() -> None:
    storyboard = build_storyboard(_movie())

    assert all(shot.subtitle == "" for shot in storyboard.shots)


def test_the_narration_duration_comes_from_the_cues_when_no_audio_is_given() -> None:
    storyboard = build_storyboard(_movie(), cues=_cues())

    assert storyboard.narration_duration == 9.0


def test_the_audio_metadata_duration_wins_over_the_cues() -> None:
    storyboard = build_storyboard(
        _movie(), cues=_cues(), audio_source="narration.mp3", audio_duration=66.7
    )

    assert storyboard.narration_duration == 66.7


# --- audio segments --------------------------------------------------------


def test_each_shot_points_at_its_slice_of_the_narration() -> None:
    storyboard = build_storyboard(
        _movie(), audio_source="output/audio/narration.mp3", audio_duration=60.0
    )

    segment = storyboard.shots[1].audio_segment
    assert segment.source == "output/audio/narration.mp3"
    assert (segment.start, segment.end) == (3.0, 6.0)
    assert segment.duration == 3.0


def test_a_segment_is_clipped_to_the_real_track_length() -> None:
    """Shots may outrun the narration; the slice must not point past its end."""
    storyboard = build_storyboard(_movie(), audio_source="narration.mp3", audio_duration=4.0)

    assert storyboard.shots[-1].audio_segment.end == 4.0


def test_without_an_audio_source_the_segment_is_empty() -> None:
    storyboard = build_storyboard(_movie())

    assert storyboard.shots[0].audio_segment.source == ""


# --- drift -----------------------------------------------------------------


def test_drift_reports_shots_running_longer_than_the_narration() -> None:
    storyboard = build_storyboard(_movie(), audio_source="a.mp3", audio_duration=5.0)

    assert storyboard.total_duration == 9.0
    assert storyboard.drift == 4.0


def test_drift_is_negative_when_the_narration_outlasts_the_shots() -> None:
    storyboard = build_storyboard(_movie(), audio_source="a.mp3", audio_duration=20.0)

    assert storyboard.drift == -11.0


def test_drift_is_zero_without_narration() -> None:
    assert build_storyboard(_movie()).drift == 0.0


# --- prompts ---------------------------------------------------------------


def test_the_image_prompt_describes_a_still_not_motion() -> None:
    storyboard = build_storyboard(_movie(), profiles=_profiles())
    prompt = storyboard.shots[0].image_prompt

    assert prompt.startswith("Lâm Thiên")  # identity from the library
    assert STILL_DIRECTIVE in prompt
    assert "slow push in" not in prompt  # camera motion belongs to the video prompt


def test_the_image_prompt_carries_framing_lighting_and_setting() -> None:
    prompt = build_storyboard(_movie(), profiles=_profiles()).shots[0].image_prompt

    assert "medium shot" in prompt
    assert "rule of thirds" in prompt
    assert "hard key" in prompt
    assert "Cliff, sunrise over the sea" in prompt
    assert prompt.endswith("negative: inconsistent face, blurry")


def test_the_video_prompt_is_passed_through_untouched() -> None:
    storyboard = build_storyboard(_movie(), profiles=_profiles())

    assert storyboard.shots[0].video_prompt == "a composed video prompt"


def test_without_a_library_the_image_prompt_still_builds() -> None:
    prompt = build_storyboard(_movie()).shots[0].image_prompt

    assert "medium shot" in prompt
    assert STILL_DIRECTIVE in prompt
    assert "negative:" not in prompt


# --- narration parsing -----------------------------------------------------


def test_srt_cues_are_parsed_with_their_text() -> None:
    srt = (
        "1\n00:00:00,000 --> 00:00:02,500\nNgày ấy trời rất trong.\n\n"
        "2\n00:00:02,500 --> 00:00:05,000\nAnh bước lên vách đá.\n"
    )

    cues = parse_narration(srt)

    assert len(cues) == 2
    assert cues[0].start == 0.0
    assert cues[0].end == 2.5
    assert cues[0].text == "Ngày ấy trời rất trong."


def test_a_multi_line_cue_is_joined() -> None:
    srt = "1\n00:00:00,000 --> 00:00:02,000\nfirst line\nsecond line\n"

    assert parse_narration(srt)[0].text == "first line second line"


def test_malformed_blocks_are_skipped() -> None:
    srt = "not a cue\n\n1\n00:00:01,000 --> 00:00:02,000\nreal cue\n"

    cues = parse_narration(srt)

    assert len(cues) == 1
    assert cues[0].text == "real cue"


def test_narration_span_is_the_last_cue_end() -> None:
    assert narration_span(_cues()) == 9.0
    assert narration_span([]) == 0.0


# --- schema ----------------------------------------------------------------


def test_the_storyboard_json_shape_matches_the_specification() -> None:
    storyboard = build_storyboard(_movie(), cues=_cues(), audio_source="a.mp3")

    payload = json.loads(json.dumps(storyboard.model_dump(), ensure_ascii=False))

    assert set(payload["shots"][0]) == STORYBOARD_FIELDS
    assert set(payload["shots"][0]["audio_segment"]) == {"source", "start", "end"}


def test_a_storyboard_round_trips_through_json() -> None:
    storyboard = build_storyboard(_movie(), cues=_cues())

    restored = Storyboard.model_validate(json.loads(json.dumps(storyboard.model_dump())))

    assert restored == storyboard


def test_storyboard_shots_are_immutable() -> None:
    shot = build_storyboard(_movie()).shots[0]

    with pytest.raises(ValidationError):
        shot.camera = "changed"  # type: ignore[misc]


def test_a_shot_requires_a_positive_duration() -> None:
    with pytest.raises(ValidationError):
        StoryboardShot(id=1, scene_id=1, order=1, duration=0)
