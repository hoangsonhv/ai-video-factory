"""Tests for the character library domain value objects and their JSON schema."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ai_video_factory.domain.value_objects.character_library import (
    CharacterLibrary,
    CharacterProfile,
    NormalizedAppearance,
    NormalizedOutfit,
)


def _profile() -> CharacterProfile:
    return CharacterProfile(
        id="lin_tian",
        master_prompt="Lâm Thiên, long black hair",
        negative_prompt="inconsistent face",
        seed=123456,
        appearance=NormalizedAppearance(hair="long black hair", eyes="golden eyes"),
        outfit=NormalizedOutfit(clothes="white silk robe"),
        voice_profile="young male, calm",
    )


def test_profile_defaults_match_the_documented_schema() -> None:
    profile = CharacterProfile(id="lin_tian")

    assert profile.reference_image is None
    assert profile.version == 1
    assert profile.seed == 0
    assert profile.appearance == NormalizedAppearance()
    assert profile.outfit == NormalizedOutfit()


def test_library_serializes_to_the_documented_json_shape() -> None:
    payload = json.loads(
        json.dumps(CharacterLibrary(characters=(_profile(),)).model_dump(), ensure_ascii=False)
    )

    assert set(payload) == {"characters"}
    assert set(payload["characters"][0]) == {
        "id",
        "master_prompt",
        "negative_prompt",
        "seed",
        "reference_image",
        "appearance",
        "outfit",
        "voice_profile",
        "version",
    }
    assert payload["characters"][0]["master_prompt"] == "Lâm Thiên, long black hair"


def test_library_round_trips_through_json() -> None:
    library = CharacterLibrary(characters=(_profile(),))

    assert CharacterLibrary.model_validate(json.loads(json.dumps(library.model_dump()))) == library


def test_profiles_are_immutable() -> None:
    with pytest.raises(ValidationError):
        _profile().master_prompt = "changed"  # type: ignore[misc]


def test_profile_requires_a_non_empty_id() -> None:
    with pytest.raises(ValidationError):
        CharacterProfile(id="")


def test_profile_rejects_a_negative_seed() -> None:
    with pytest.raises(ValidationError):
        CharacterProfile(id="lin_tian", seed=-1)
