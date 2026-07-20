"""Tests for the director domain models and the directed-movie JSON schema."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ai_video_factory.domain.value_objects.director import (
    MAX_SHOT_SECONDS,
    MIN_SHOT_SECONDS,
    DirectedMovie,
    DirectedScene,
    Shot,
)
from ai_video_factory.domain.value_objects.movie import Camera, Movie, Scene

SHOT_FIELDS = {
    "id",
    "duration",
    "camera",
    "camera_motion",
    "lens",
    "framing",
    "subject",
    "action",
    "expression",
    "environment_motion",
    "lighting",
    "transition",
    "video_prompt",
}


def _shot(shot_id: int = 1, duration: int = 3) -> Shot:
    return Shot(
        id=shot_id,
        duration=duration,
        camera="medium shot",
        camera_motion="slow push in",
        lens="50mm",
        framing="rule of thirds",
        subject="lin_tian",
        action="draws a sword",
        expression="resolve hardening",
        environment_motion="embers drifting",
        lighting="hard key from the left",
        transition="cut",
        video_prompt="a composed prompt",
    )


def test_a_shot_carries_exactly_the_documented_fields() -> None:
    assert set(Shot.model_fields) == SHOT_FIELDS


def test_a_shot_duration_must_sit_in_the_permitted_range() -> None:
    assert _shot(duration=MIN_SHOT_SECONDS).duration == MIN_SHOT_SECONDS
    assert _shot(duration=MAX_SHOT_SECONDS).duration == MAX_SHOT_SECONDS
    with pytest.raises(ValidationError):
        _shot(duration=MIN_SHOT_SECONDS - 1)
    with pytest.raises(ValidationError):
        _shot(duration=MAX_SHOT_SECONDS + 1)


def test_a_shot_id_starts_at_one() -> None:
    with pytest.raises(ValidationError):
        _shot(shot_id=0)


def test_shots_are_immutable() -> None:
    with pytest.raises(ValidationError):
        _shot().camera = "changed"  # type: ignore[misc]


def test_a_directed_scene_keeps_every_original_scene_field() -> None:
    scene = Scene(
        id=1,
        duration=9,
        location="cliff",
        characters=("lin_tian",),
        camera=Camera(shot="wide", movement="drone", lens="35mm"),
        action="walks",
        emotion="fear",
        dialogue="Có ai không?",
        image_prompt="an image prompt",
        video_prompt="a video prompt",
    )

    directed = DirectedScene.model_validate(scene.model_dump())

    assert set(Scene.model_fields).issubset(set(DirectedScene.model_fields))
    assert directed.dialogue == "Có ai không?"
    assert directed.camera.movement == "drone"
    assert directed.shots == ()  # unplanned until directed
    assert not directed.is_planned


def test_a_planned_scene_reports_its_shots_and_running_time() -> None:
    scene = DirectedScene(id=1, duration=9, shots=(_shot(1, 3), _shot(2, 4)))

    assert scene.is_planned
    assert scene.shot_seconds == 7


def test_a_directed_movie_counts_every_shot() -> None:
    movie = DirectedMovie(
        title="Tu Tiên",
        duration=60,
        scenes=(
            DirectedScene(id=1, duration=9, shots=(_shot(1), _shot(2), _shot(3))),
            DirectedScene(id=2, duration=6, shots=(_shot(1), _shot(2))),
        ),
    )

    assert movie.shot_count == 5


def test_a_directed_movie_is_still_a_valid_movie() -> None:
    """The directed document must stay readable by every existing stage."""
    directed = DirectedMovie(
        title="Tu Tiên", duration=60, scenes=(DirectedScene(id=1, duration=9, shots=(_shot(),)),)
    )

    payload = json.loads(json.dumps(directed.model_dump(), ensure_ascii=False))
    restored = Movie.model_validate(payload)  # the base schema still validates

    assert restored.title == "Tu Tiên"
    assert len(restored.scenes) == 1


def test_the_directed_json_shape_matches_the_specification() -> None:
    directed = DirectedMovie(
        title="Tu Tiên", duration=60, scenes=(DirectedScene(id=1, duration=9, shots=(_shot(),)),)
    )

    payload = json.loads(json.dumps(directed.model_dump(), ensure_ascii=False))
    scene = payload["scenes"][0]

    assert set(scene["shots"][0]) == SHOT_FIELDS
    assert scene["shots"][0]["environment_motion"] == "embers drifting"
    assert scene["shots"][0]["duration"] == 3


def test_a_directed_movie_round_trips_through_json() -> None:
    directed = DirectedMovie(
        title="Tu Tiên",
        duration=60,
        scenes=(DirectedScene(id=1, duration=9, shots=(_shot(1), _shot(2))),),
    )

    restored = DirectedMovie.model_validate(json.loads(json.dumps(directed.model_dump())))

    assert restored == directed
