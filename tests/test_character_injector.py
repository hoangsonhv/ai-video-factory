"""Tests for the character prompt injector."""

from __future__ import annotations

import pytest

from ai_video_factory.domain.value_objects.character_library import (
    CharacterLibrary,
    CharacterProfile,
)
from ai_video_factory.domain.value_objects.movie import Camera, Movie, Scene
from ai_video_factory.infrastructure.character.errors import CharacterLibraryError
from ai_video_factory.infrastructure.character.injector import CharacterPromptInjector

_ORIGINAL = "standing on a cliff at sunrise"


def _library() -> CharacterLibrary:
    return CharacterLibrary(
        characters=(
            CharacterProfile(
                id="lin_tian",
                master_prompt="Lâm Thiên, long black hair, consistent character design",
                negative_prompt="inconsistent face, blurry",
                seed=1234,
            ),
            CharacterProfile(
                id="ma_nu",
                master_prompt="Ma Nữ, white hair, consistent character design",
                negative_prompt="inconsistent face, extra fingers",
                seed=5678,
            ),
        )
    )


def _movie(*scenes: Scene) -> Movie:
    return Movie(title="Tu Tiên", duration=60, scenes=scenes)


def _scene(**overrides: object) -> Scene:
    defaults: dict[str, object] = {
        "id": 1,
        "duration": 5,
        "characters": ("lin_tian",),
        "camera": Camera(shot="wide"),
        "image_prompt": _ORIGINAL,
        "video_prompt": "camera pushes in slowly",
    }
    defaults.update(overrides)
    return Scene.model_validate(defaults)


def test_inject_prepends_master_prompt_and_appends_negative_prompt() -> None:
    injected = CharacterPromptInjector(_library()).inject(_movie(_scene()))
    prompt = injected.scenes[0].image_prompt

    assert prompt.startswith("Lâm Thiên, long black hair, consistent character design | ")
    assert _ORIGINAL in prompt  # the scene's own direction is preserved
    assert prompt.endswith("| negative: inconsistent face, blurry")


def test_inject_rewrites_the_video_prompt_too() -> None:
    injected = CharacterPromptInjector(_library()).inject(_movie(_scene()))
    prompt = injected.scenes[0].video_prompt

    assert prompt.startswith("Lâm Thiên, long black hair")
    assert "camera pushes in slowly" in prompt


def test_inject_combines_every_character_in_the_scene_and_dedupes_negatives() -> None:
    injected = CharacterPromptInjector(_library()).inject(
        _movie(_scene(characters=("lin_tian", "ma_nu")))
    )
    prompt = injected.scenes[0].image_prompt

    assert "Lâm Thiên" in prompt
    assert "Ma Nữ" in prompt
    assert prompt.count("inconsistent face") == 1


def test_inject_leaves_scenes_without_characters_untouched() -> None:
    scene = _scene(characters=())
    injected = CharacterPromptInjector(_library()).inject(_movie(scene))

    assert injected.scenes[0] == scene


def test_inject_is_idempotent() -> None:
    injector = CharacterPromptInjector(_library())
    once = injector.inject(_movie(_scene()))

    assert injector.inject(once) == once


def test_inject_preserves_everything_but_the_prompts() -> None:
    movie = _movie(_scene(action="draws a sword", dialogue="Có ai không?"))
    injected = CharacterPromptInjector(_library()).inject(movie)

    assert injected.title == movie.title
    assert injected.characters == movie.characters
    assert injected.scenes[0].action == "draws a sword"
    assert injected.scenes[0].dialogue == "Có ai không?"
    assert injected.scenes[0].camera == movie.scenes[0].camera


def test_inject_unknown_character_raises() -> None:
    with pytest.raises(CharacterLibraryError, match="unknown character"):
        CharacterPromptInjector(_library()).inject(_movie(_scene(characters=("ghost",))))
