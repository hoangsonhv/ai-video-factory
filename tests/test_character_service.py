"""Tests for the deterministic character consistency service."""

from __future__ import annotations

import pytest

from ai_video_factory.domain.value_objects.character_library import CharacterLibrary
from ai_video_factory.domain.value_objects.movie import Appearance, Character, Movie, Scene
from ai_video_factory.infrastructure.character.errors import CharacterLibraryError
from ai_video_factory.infrastructure.character.service import (
    SEED_MODULO,
    CharacterConsistencyService,
    generate_master_prompt,
    generate_negative_prompt,
    generate_seed,
    merge_duplicates,
    normalize_appearance,
    normalize_outfit,
    normalize_text,
)


def _character(**overrides: object) -> Character:
    defaults: dict[str, object] = {
        "id": "lin_tian",
        "name": "Lâm Thiên",
        "gender": "male",
        "age": 18,
        "appearance": Appearance(
            hair="Long  black hair.",
            eyes="golden eyes",
            face="sharp jawline",
            body="slim",
            clothes="white silk robe",
            accessories="jade hairpin",
        ),
        "voice": "young male, calm",
    }
    defaults.update(overrides)
    return Character.model_validate(defaults)


def _movie(*characters: Character) -> Movie:
    return Movie(
        title="Tu Tiên",
        duration=60,
        characters=characters,
        scenes=(Scene(id=1, duration=5),),
    )


# --- normalization ---------------------------------------------------------


def test_normalize_text_collapses_whitespace_punctuation_and_case() -> None:
    assert normalize_text("  Long   BLACK hair. ") == "long black hair"


def test_normalize_appearance_splits_physical_traits_from_outfit() -> None:
    character = _character()
    appearance = normalize_appearance(character)
    outfit = normalize_outfit(character)

    assert appearance.hair == "long black hair"
    assert appearance.eyes == "golden eyes"
    assert outfit.clothes == "white silk robe"
    assert outfit.accessories == "jade hairpin"
    # clothing never leaks into the permanent physical appearance
    assert "robe" not in appearance.model_dump_json()


# --- seed generation -------------------------------------------------------


def test_generate_seed_is_deterministic_and_in_range() -> None:
    assert generate_seed("lin_tian") == generate_seed("lin_tian")
    assert 0 <= generate_seed("lin_tian") < SEED_MODULO


def test_generate_seed_ignores_case_and_surrounding_space() -> None:
    assert generate_seed("Lin_Tian") == generate_seed(" lin_tian ")


def test_generate_seed_differs_between_characters() -> None:
    assert generate_seed("lin_tian") != generate_seed("ma_nu")


# --- prompt generation -----------------------------------------------------


def test_master_prompt_contains_every_trait_and_the_consistency_clause() -> None:
    character = _character()
    prompt = generate_master_prompt(
        character, normalize_appearance(character), normalize_outfit(character)
    )

    assert prompt.startswith("Lâm Thiên, male, 18 years old")
    for expected in ("long black hair", "golden eyes", "wearing white silk robe", "jade hairpin"):
        assert expected in prompt
    assert "identical face and outfit in every scene" in prompt


def test_master_prompt_omits_empty_traits() -> None:
    character = _character(gender="", age=0, appearance=Appearance(hair="black hair"))
    prompt = generate_master_prompt(
        character, normalize_appearance(character), normalize_outfit(character)
    )

    assert prompt.startswith("Lâm Thiên, black hair,")
    assert "wearing" not in prompt
    assert ", ," not in prompt


def test_negative_prompt_merges_base_terms_with_the_character_terms() -> None:
    negative = generate_negative_prompt(_character(negative_prompt="modern clothes, blurry"))

    assert "inconsistent face" in negative
    assert "modern clothes" in negative
    assert negative.count("blurry") == 1  # deduplicated against the base terms


# --- duplicate merging -----------------------------------------------------


def test_merge_duplicates_collapses_the_same_id_keeping_the_first_appearance() -> None:
    first = _character()
    later = _character(appearance=Appearance(hair="white hair", eyes="red eyes"))

    merged = merge_duplicates([first, later])

    assert len(merged) == 1
    assert merged[0].appearance.hair == "Long  black hair."  # first occurrence wins
    assert merged[0].appearance.eyes == "golden eyes"


def test_merge_duplicates_fills_only_traits_the_first_record_left_empty() -> None:
    first = _character(appearance=Appearance(hair="black hair"), voice="")
    later = _character(appearance=Appearance(hair="white hair", eyes="golden eyes"), voice="calm")

    merged = merge_duplicates([first, later])[0]

    assert merged.appearance.hair == "black hair"
    assert merged.appearance.eyes == "golden eyes"
    assert merged.voice == "calm"


def test_merge_duplicates_unions_negative_prompts() -> None:
    first = _character(negative_prompt="modern clothes")
    later = _character(negative_prompt="modern clothes, glasses")

    merged = merge_duplicates([first, later])[0]

    assert merged.negative_prompt == "modern clothes, glasses"


def test_merge_duplicates_keeps_distinct_characters() -> None:
    assert len(merge_duplicates([_character(), _character(id="ma_nu", name="Ma Nữ")])) == 2


# --- service ---------------------------------------------------------------


def test_build_produces_one_profile_per_character() -> None:
    library = CharacterConsistencyService().build(_movie(_character(), _character()))

    assert isinstance(library, CharacterLibrary)
    assert len(library.characters) == 1  # the duplicate was merged
    profile = library.characters[0]
    assert profile.id == "lin_tian"
    assert profile.seed == generate_seed("lin_tian")
    assert profile.voice_profile == "young male, calm"
    assert profile.reference_image is None
    assert profile.version == 1


def test_build_is_reproducible() -> None:
    movie = _movie(_character())
    service = CharacterConsistencyService()

    assert service.build(movie) == service.build(movie)


def test_build_without_characters_raises() -> None:
    with pytest.raises(CharacterLibraryError):
        CharacterConsistencyService().build(_movie())
