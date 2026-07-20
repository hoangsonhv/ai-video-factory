"""Tests for shot planning arithmetic, batch parsing and prompt composition."""

from __future__ import annotations

import json

import pytest

from ai_video_factory.domain.value_objects.character_library import CharacterProfile
from ai_video_factory.domain.value_objects.director import (
    MAX_SHOT_SECONDS,
    MIN_SHOT_SECONDS,
    Shot,
)
from ai_video_factory.domain.value_objects.movie import Camera, Location, Movie, Scene
from ai_video_factory.infrastructure.director.errors import DirectorError
from ai_video_factory.infrastructure.director.prompt_builder import (
    VIDEO_DIRECTIVE,
    build_shot_prompt,
)
from ai_video_factory.infrastructure.director.shot_parser import parse_scene_shots, parse_shot_plan
from ai_video_factory.infrastructure.director.shot_planner import (
    MAX_SHOTS,
    MIN_SHOTS,
    clamp_shot_duration,
    target_shot_count,
)


def _raw_shot(**overrides: object) -> dict[str, object]:
    shot: dict[str, object] = {
        "id": 1,
        "duration": 3,
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
        "video_prompt": "he draws the blade as embers rise",
    }
    shot.update(overrides)
    return shot


# --- shot-count arithmetic -------------------------------------------------


def test_a_normal_scene_gets_a_count_inside_the_band() -> None:
    for duration in (9, 12, 15, 20):
        count = target_shot_count(duration)
        assert MIN_SHOTS <= count <= MAX_SHOTS


def test_a_long_scene_is_capped_at_the_maximum() -> None:
    assert target_shot_count(120) == MAX_SHOTS


def test_a_short_scene_gets_only_what_it_can_hold() -> None:
    """3 shots x 2s needs 6s, so a 5s scene cannot have three."""
    assert target_shot_count(5) == 2
    assert target_shot_count(4) == 2
    assert target_shot_count(2) == 1


def test_the_count_never_asks_for_impossible_shots() -> None:
    for duration in range(2, 61):
        assert target_shot_count(duration) * MIN_SHOT_SECONDS <= max(duration, MIN_SHOT_SECONDS)


def test_durations_are_clamped_into_the_permitted_range() -> None:
    assert clamp_shot_duration(0) == MIN_SHOT_SECONDS
    assert clamp_shot_duration(99) == MAX_SHOT_SECONDS
    assert clamp_shot_duration(3) == 3


# --- batch parsing ---------------------------------------------------------


def test_a_batch_answer_is_parsed_for_every_scene() -> None:
    content = json.dumps(
        {
            "scenes": [
                {"scene_id": 1, "shots": [_raw_shot(), _raw_shot(id=2)]},
                {"scene_id": 2, "shots": [_raw_shot()]},
            ]
        }
    )

    plan = parse_shot_plan(content, {1: 9, 2: 6})

    assert sorted(plan) == [1, 2]
    assert len(plan[1]) == 2
    assert plan[1][0].camera == "medium shot"
    assert plan[1][0].action == "draws a sword"


def test_shot_ids_are_renumbered_per_scene() -> None:
    """Ordering is ours, not the model's — ids come out 1..N regardless."""
    content = json.dumps(
        {"scenes": [{"scene_id": 1, "shots": [_raw_shot(id=77), _raw_shot(id=3), _raw_shot(id=9)]}]}
    )

    plan = parse_shot_plan(content, {1: 9})

    assert [shot.id for shot in plan[1]] == [1, 2, 3]


def test_an_out_of_range_duration_is_clamped() -> None:
    content = json.dumps(
        {"scenes": [{"scene_id": 1, "shots": [_raw_shot(duration=45), _raw_shot(duration=1)]}]}
    )

    plan = parse_shot_plan(content, {1: 9})

    assert plan[1][0].duration == MAX_SHOT_SECONDS
    assert plan[1][1].duration == MIN_SHOT_SECONDS


def test_a_missing_duration_falls_back_to_an_even_split() -> None:
    content = json.dumps(
        {"scenes": [{"scene_id": 1, "shots": [_raw_shot(duration=None), _raw_shot(duration="x")]}]}
    )

    plan = parse_shot_plan(content, {1: 8})

    assert [shot.duration for shot in plan[1]] == [4, 4]


def test_more_shots_than_the_maximum_are_trimmed() -> None:
    content = json.dumps({"scenes": [{"scene_id": 1, "shots": [_raw_shot()] * 20}]})

    plan = parse_shot_plan(content, {1: 60})

    assert len(plan[1]) == MAX_SHOTS


def test_markdown_fences_are_tolerated() -> None:
    content = (
        "```json\n" + json.dumps({"scenes": [{"scene_id": 1, "shots": [_raw_shot()]}]}) + "\n```"
    )

    assert len(parse_shot_plan(content, {1: 9})[1]) == 1


def test_a_bare_array_is_accepted() -> None:
    content = json.dumps([{"scene_id": 1, "shots": [_raw_shot()]}])

    assert 1 in parse_shot_plan(content, {1: 9})


def test_a_scene_with_no_shots_is_omitted_from_the_plan() -> None:
    content = json.dumps(
        {"scenes": [{"scene_id": 1, "shots": []}, {"scene_id": 2, "shots": [_raw_shot()]}]}
    )

    plan = parse_shot_plan(content, {1: 9, 2: 9})

    assert list(plan) == [2]


def test_unknown_extra_shot_fields_are_ignored() -> None:
    content = json.dumps({"scenes": [{"scene_id": 1, "shots": [_raw_shot(vibe="???")]}]})

    assert parse_shot_plan(content, {1: 9})[1][0].camera == "medium shot"


def test_invalid_json_is_rejected() -> None:
    with pytest.raises(DirectorError, match="invalid JSON"):
        parse_shot_plan("{not json", {1: 9})


def test_an_empty_scenes_array_is_rejected() -> None:
    with pytest.raises(DirectorError, match="no scenes"):
        parse_shot_plan('{"scenes":[]}', {1: 9})


def test_an_answer_with_no_usable_shots_is_rejected() -> None:
    with pytest.raises(DirectorError, match="no usable shots"):
        parse_shot_plan('{"scenes":[{"scene_id":1,"shots":[]}]}', {1: 9})


def test_parse_scene_shots_handles_one_block() -> None:
    shots = parse_scene_shots({"scene_id": 1, "shots": [_raw_shot()]}, 9)

    assert len(shots) == 1
    assert shots[0].lens == "50mm"


# --- prompt composition ----------------------------------------------------


def _movie() -> Movie:
    return Movie(
        title="Tu Tiên",
        style="cinematic",
        duration=60,
        locations=(Location(id="cliff", name="Cliff", description="sunrise over the sea"),),
    )


def _scene(**overrides: object) -> Scene:
    defaults: dict[str, object] = {
        "id": 1,
        "duration": 9,
        "location": "cliff",
        "characters": ("lin_tian",),
        "camera": Camera(shot="wide shot", movement="drone", lens="35mm"),
        "action": "draws a sword",
        "emotion": "resolve",
    }
    defaults.update(overrides)
    return Scene.model_validate(defaults)


def _profiles() -> dict[str, CharacterProfile]:
    return {
        "lin_tian": CharacterProfile(
            id="lin_tian",
            master_prompt="Lâm Thiên, long black hair, consistent character design",
            negative_prompt="inconsistent face, blurry",
        )
    }


def _locations() -> dict[str, Location]:
    return {location.id: location for location in _movie().locations}


def _shot(**overrides: object) -> Shot:
    return Shot.model_validate(_raw_shot(**overrides))


def test_the_prompt_leads_with_the_character_master_prompt() -> None:
    prompt = build_shot_prompt(_movie(), _scene(), _shot(), _profiles(), _locations())

    assert prompt.startswith("Lâm Thiên, long black hair, consistent character design")


def test_the_prompt_carries_the_camera_setup() -> None:
    prompt = build_shot_prompt(_movie(), _scene(), _shot(), _profiles(), _locations())

    for expected in ("medium shot", "slow push in", "50mm", "rule of thirds"):
        assert expected in prompt


def test_the_prompt_carries_the_motion_and_expression() -> None:
    prompt = build_shot_prompt(_movie(), _scene(), _shot(), _profiles(), _locations())

    assert "action: draws a sword" in prompt
    assert "expression: resolve hardening" in prompt
    assert "Environment: embers drifting" in prompt


def test_the_prompt_folds_in_the_models_own_description() -> None:
    prompt = build_shot_prompt(_movie(), _scene(), _shot(), _profiles(), _locations())

    assert "he draws the blade as embers rise" in prompt


def test_the_prompt_targets_video_not_images() -> None:
    prompt = build_shot_prompt(_movie(), _scene(), _shot(), _profiles(), _locations())

    assert VIDEO_DIRECTIVE in prompt
    assert "3s" in prompt  # the shot's own length


def test_the_prompt_carries_the_setting_and_appends_negatives() -> None:
    prompt = build_shot_prompt(_movie(), _scene(), _shot(), _profiles(), _locations())

    assert "Cliff, sunrise over the sea" in prompt
    assert prompt.endswith("negative: inconsistent face, blurry")


def test_empty_shot_fields_are_omitted_rather_than_padded() -> None:
    sparse = _shot(lens="", framing="", environment_motion="", lighting="", transition="")

    prompt = build_shot_prompt(_movie(), _scene(), sparse, _profiles(), _locations())

    assert "medium shot" in prompt
    assert "Environment:" not in prompt
    assert "Transition:" not in prompt
    assert " | : " not in prompt


def test_a_shot_without_a_library_profile_still_gets_a_prompt() -> None:
    prompt = build_shot_prompt(_movie(), _scene(), _shot(), {}, _locations())

    assert "medium shot" in prompt
    assert VIDEO_DIRECTIVE in prompt
    assert "negative:" not in prompt


def test_multiple_characters_are_combined_and_negatives_deduped() -> None:
    profiles = _profiles()
    profiles["ma_nu"] = CharacterProfile(
        id="ma_nu", master_prompt="Ma Nữ, white hair", negative_prompt="inconsistent face, extra"
    )

    prompt = build_shot_prompt(
        _movie(), _scene(characters=("lin_tian", "ma_nu")), _shot(), profiles, _locations()
    )

    assert "Lâm Thiên" in prompt
    assert "Ma Nữ" in prompt
    assert prompt.count("inconsistent face") == 1
