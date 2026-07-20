"""Tests for the Movie domain value objects (schema + immutability)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_video_factory.domain.value_objects.movie import (
    Appearance,
    Camera,
    Character,
    Location,
    Movie,
    Scene,
)


def _character(cid: str = "hero") -> Character:
    return Character(
        id=cid,
        name="Hero",
        gender="male",
        age=25,
        appearance=Appearance(hair="black", eyes="brown", clothes="armor"),
        personality="brave",
        voice="deep",
        negative_prompt="blurry",
    )


def _scene(sid: int = 1) -> Scene:
    return Scene(
        id=sid,
        duration=5,
        location="cemetery",
        characters=("hero",),
        camera=Camera(shot="close-up", movement="dolly", lens="50mm"),
        action="draw sword",
        emotion="determined",
        dialogue="Xin chào",
        image_prompt="a hero",
        video_prompt="hero draws sword",
    )


def test_full_movie_validates() -> None:
    movie = Movie(
        title="Test",
        genre="action",
        style="cinematic",
        duration=60,
        characters=(_character(),),
        locations=(Location(id="cemetery", name="Cemetery", description="dark"),),
        scenes=(_scene(1), _scene(2)),
    )
    assert movie.characters[0].appearance.hair == "black"
    assert movie.scenes[0].camera.shot == "close-up"
    assert len(movie.scenes) == 2


def test_defaults_are_applied() -> None:
    character = Character(id="x", name="X")
    assert character.age == 0
    assert character.appearance == Appearance()
    scene = Scene(id=1, duration=3)
    assert scene.characters == ()
    assert scene.camera == Camera()


def test_movie_is_immutable() -> None:
    movie = Movie(title="T", duration=10)
    with pytest.raises(ValidationError):
        movie.title = "changed"  # type: ignore[misc]


def test_scene_duration_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Scene(id=1, duration=0)


def test_character_requires_id_and_name() -> None:
    with pytest.raises(ValidationError):
        Character(id="", name="X")


def test_round_trips_through_json() -> None:
    movie = Movie(
        title="T",
        duration=30,
        characters=(_character(),),
        locations=(Location(id="l", name="L"),),
        scenes=(_scene(),),
    )
    restored = Movie.model_validate(movie.model_dump())
    assert restored == movie
