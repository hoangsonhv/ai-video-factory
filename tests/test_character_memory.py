"""Tests for the character memory engine: canon, references, validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_video_factory.domain.value_objects.character_memory import (
    AppearanceScore,
    CharacterMemory,
    CharacterMemoryDocument,
)
from ai_video_factory.domain.value_objects.continuity import CharacterBible, CharacterBibleEntry
from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.domain.value_objects.movie import Character, Movie
from ai_video_factory.domain.value_objects.storyboard import Storyboard, StoryboardShot
from ai_video_factory.infrastructure.memory.builder import (
    adopt_references,
    derive_memory,
    first_image_for,
    merge_memory,
)
from ai_video_factory.infrastructure.memory.engine import CharacterMemoryEngine
from ai_video_factory.infrastructure.memory.enricher import (
    PROVIDERS_WITH_IMAGE_REFERENCE,
    enrich_prompt,
    supports_image_reference,
)
from ai_video_factory.infrastructure.memory.errors import CharacterMemoryError
from ai_video_factory.infrastructure.memory.validator import AppearanceValidator


def _bible() -> CharacterBible:
    return CharacterBible(
        characters=(
            CharacterBibleEntry(
                id="lin_tian",
                name="Lâm Thiên",
                appearance="long black hair, golden eyes, sharp jaw",
                wardrobe="white silk robe",
                signature_props="jade pendant, celestial sword",
                palette="white and gold",
            ),
            CharacterBibleEntry(
                id="ma_nu", name="Ma Nữ", appearance="white hair", wardrobe="dark cloak"
            ),
        )
    )


def _movie() -> Movie:
    return Movie(
        title="Tu Tiên",
        style="cinematic",
        duration=60,
        characters=(
            Character(id="lin_tian", name="Lâm Thiên", gender="male", age=22, personality="calm"),
            Character(id="ma_nu", name="Ma Nữ", gender="female", age=19),
        ),
    )


def _storyboard(*characters: str) -> Storyboard:
    names = characters or ("lin_tian", "ma_nu", "lin_tian")
    shots = tuple(
        StoryboardShot(
            id=index,
            scene_id=index,
            order=1,
            duration=3,
            character=name,
            action=f"action {index}",
        )
        for index, name in enumerate(names, start=1)
    )
    return Storyboard(title="Tu Tiên", shots=shots)


def _memory() -> CharacterMemoryDocument:
    return derive_memory(_bible(), _movie(), style="cinematic")


def _prompt(scene_number: int, text: str) -> ImagePrompt:
    return ImagePrompt(
        scene_number=scene_number, prompt=text, aspect_ratio="9:16", style="cinematic"
    )


# --- deriving the canon ----------------------------------------------------


def test_the_canon_splits_appearance_into_its_parts() -> None:
    memory = _memory().get("lin_tian")

    assert memory is not None
    assert memory.canonical_hair == "long black hair"
    assert "golden eyes" in memory.canonical_face
    assert memory.canonical_clothes == "white silk robe"
    assert memory.canonical_color_palette == "white and gold"


def test_a_weapon_is_pinned_separately_from_other_props() -> None:
    memory = _memory().get("lin_tian")

    assert memory is not None
    assert "celestial sword" in memory.canonical_weapon
    assert "jade pendant" not in memory.canonical_weapon


def test_gender_and_age_come_from_the_movie() -> None:
    memory = _memory().get("lin_tian")

    assert memory is not None
    assert memory.gender == "male"
    assert memory.age == "22"
    assert memory.style == "cinematic"


def test_the_hash_fingerprints_the_canonical_look() -> None:
    memory = _memory().get("lin_tian")

    assert memory is not None
    assert memory.appearance_hash
    assert memory.appearance_hash == memory.compute_hash()
    assert not memory.is_drifted


def test_a_changed_appearance_is_detected_as_drift() -> None:
    original = _memory().get("lin_tian")
    assert original is not None

    tampered = original.model_copy(update={"canonical_hair": "silver hair"})

    assert tampered.is_drifted


def test_the_summary_reads_as_one_identity_line() -> None:
    memory = _memory().get("lin_tian")

    assert memory is not None
    assert "long black hair" in memory.summary
    assert "white silk robe" in memory.summary


# --- remembering across runs ----------------------------------------------


def test_a_remembered_canon_is_never_overwritten() -> None:
    """This is what makes it a memory rather than a re-derivation."""
    remembered = CharacterMemoryDocument(
        characters=(
            CharacterMemory(character_id="lin_tian", canonical_hair="silver hair (hand-edited)"),
        )
    )

    merged = merge_memory(remembered, _memory())
    entry = merged.get("lin_tian")

    assert entry is not None
    assert entry.canonical_hair == "silver hair (hand-edited)"


def test_gaps_in_a_remembered_canon_are_filled() -> None:
    remembered = CharacterMemoryDocument(
        characters=(CharacterMemory(character_id="lin_tian", canonical_hair="silver hair"),)
    )

    entry = merge_memory(remembered, _memory()).get("lin_tian")

    assert entry is not None
    assert entry.canonical_clothes == "white silk robe"  # was empty, now filled


def test_a_new_character_is_added_to_the_memory() -> None:
    remembered = CharacterMemoryDocument(characters=(CharacterMemory(character_id="lin_tian"),))

    merged = merge_memory(remembered, _memory())

    assert merged.get("ma_nu") is not None


def test_a_character_no_longer_in_the_bible_is_kept() -> None:
    """Forgetting a character would silently free its look to drift."""
    remembered = CharacterMemoryDocument(
        characters=(CharacterMemory(character_id="retired_hero", canonical_hair="grey"),)
    )

    merged = merge_memory(remembered, _memory())

    assert merged.get("retired_hero") is not None


# --- reference adoption ----------------------------------------------------


def test_the_first_image_of_a_character_is_adopted(tmp_path: Path) -> None:
    images = {1: tmp_path / "001.png", 3: tmp_path / "003.png"}

    adopted = adopt_references(_memory(), _storyboard(), images)
    entry = adopted.get("lin_tian")

    assert entry is not None
    assert entry.reference_image == str(tmp_path / "001.png")  # shot 1, not shot 3


def test_an_adopted_reference_is_never_replaced(tmp_path: Path) -> None:
    """Re-pointing it would redefine the character mid-film."""
    memory = CharacterMemoryDocument(
        characters=(
            CharacterMemory(character_id="lin_tian", reference_image="output/images/001.png"),
        )
    )

    adopted = adopt_references(memory, _storyboard(), {1: tmp_path / "999.png"})
    entry = adopted.get("lin_tian")

    assert entry is not None
    assert entry.reference_image == "output/images/001.png"


def test_a_character_with_no_image_gets_no_reference() -> None:
    adopted = adopt_references(_memory(), _storyboard(), {})

    assert all(not c.has_reference for c in adopted.characters)


def test_the_first_image_lookup_follows_timeline_order(tmp_path: Path) -> None:
    storyboard = _storyboard("ma_nu", "lin_tian", "lin_tian")
    images = {2: tmp_path / "002.png", 3: tmp_path / "003.png"}

    assert first_image_for(storyboard, "lin_tian", images) == tmp_path / "002.png"


# --- provider capability ---------------------------------------------------


def test_no_shipped_image_driver_takes_a_reference_image() -> None:
    """Wiring one is a provider change, which this sprint may not make."""
    assert not supports_image_reference("pollinations")
    assert not supports_image_reference("gemini_imagen")
    assert frozenset() == PROVIDERS_WITH_IMAGE_REFERENCE


def test_a_driver_without_reference_support_gets_a_description() -> None:
    memory = _memory().get("lin_tian")
    assert memory is not None
    memory = memory.model_copy(update={"reference_image": "output/images/001.png"})

    prompt = enrich_prompt("base", memory, provider="pollinations")

    assert "match the established look" in prompt
    assert "output/images/001.png" in prompt
    assert "(attached)" not in prompt


def test_a_driver_with_reference_support_gets_the_path_attached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ai_video_factory.infrastructure.memory import enricher

    monkeypatch.setattr(enricher, "PROVIDERS_WITH_IMAGE_REFERENCE", frozenset({"future_driver"}))
    memory = _memory().get("lin_tian")
    assert memory is not None
    memory = memory.model_copy(update={"reference_image": "output/images/001.png"})

    prompt = enricher.enrich_prompt("base", memory, provider="future_driver")

    assert "(attached)" in prompt


# --- prompt enrichment -----------------------------------------------------


def test_the_prompt_carries_reference_appearance_and_history() -> None:
    memory = _memory().get("lin_tian")
    assert memory is not None

    prompt = enrich_prompt("base prompt", memory, previous_appearance="as first rendered")

    assert "Reference Image:" in prompt
    assert "Appearance Summary:" in prompt
    assert "Previous Generated Appearance:" in prompt
    assert "base prompt" in prompt  # the continuity prompt is preserved


def test_the_first_image_is_told_it_will_become_the_reference() -> None:
    memory = _memory().get("lin_tian")
    assert memory is not None

    prompt = enrich_prompt("base", memory)

    assert "becomes the canonical reference" in prompt


def test_escalation_genuinely_rewrites_the_prompt() -> None:
    memory = _memory().get("lin_tian")
    assert memory is not None

    level0 = enrich_prompt("base", memory, level=0)
    level1 = enrich_prompt("base", memory, level=1)
    level2 = enrich_prompt("base", memory, level=2)

    assert level1 != level0
    assert level2 != level1
    assert "Identity lock" in level1
    assert "Gender:" in level2


# --- validation ------------------------------------------------------------


def test_a_prompt_restating_the_canon_scores_full_marks() -> None:
    memory = _memory().get("lin_tian")
    assert memory is not None

    score = AppearanceValidator().validate(
        enrich_prompt("base", memory, level=2), memory, shot_id=1
    )

    assert score.total == 100
    assert not score.issues


def test_a_prompt_ignoring_the_canon_scores_zero() -> None:
    """The validator must be able to fail, or it measures nothing."""
    memory = _memory().get("lin_tian")
    assert memory is not None

    score = AppearanceValidator().validate("a person standing", memory, shot_id=1)

    assert score.total == 0
    assert "hair" in score.issues


def test_an_attribute_the_memory_never_captured_counts_against_the_score() -> None:
    """A character with no recorded weapon really will grow different ones."""
    memory = _memory().get("ma_nu")
    assert memory is not None

    score = AppearanceValidator().validate(
        enrich_prompt("base", memory, level=2), memory, shot_id=1
    )

    assert score.weapon == 0
    assert "weapon (not remembered)" in score.issues
    assert score.total < 100


def test_the_total_is_the_mean_of_the_eight_attributes() -> None:
    score = AppearanceScore(
        shot_id=1,
        hair=100,
        face=100,
        clothes=100,
        weapon=0,
        colors=100,
        gender=100,
        age=100,
        style=100,
    )

    assert score.total == 88
    assert not score.passed(90)


# --- the engine ------------------------------------------------------------


def test_the_engine_enriches_every_prompt() -> None:
    prompts = tuple(_prompt(index, f"base {index}") for index in (1, 2, 3))

    result = CharacterMemoryEngine().run(_storyboard(), prompts, _memory())

    assert len(result.prompts) == 3
    assert all("Appearance Summary:" in prompt.prompt for prompt in result.prompts)


def test_the_engine_scores_every_enriched_prompt() -> None:
    prompts = tuple(_prompt(i, f"base {i}") for i in (1, 2, 3))

    result = CharacterMemoryEngine().run(_storyboard(), prompts, _memory())

    assert len(result.scores.scores) == 3
    assert result.scores.average > 0


def test_a_prompt_that_cannot_pass_is_rebuilt_then_reported() -> None:
    prompts = (_prompt(2, "base"),)  # shot 2 is ma_nu, who has no weapon

    result = CharacterMemoryEngine(threshold=100).run(_storyboard(), prompts, _memory())

    assert result.scores.scores[0].attempts == 3
    assert result.scores.failing


def test_a_passing_prompt_is_not_rebuilt() -> None:
    prompts = (_prompt(1, "base"),)

    result = CharacterMemoryEngine(threshold=0).run(_storyboard(), prompts, _memory())

    assert result.scores.scores[0].attempts == 1


def test_a_shot_with_no_remembered_character_is_left_alone() -> None:
    storyboard = _storyboard("nobody")
    prompts = (_prompt(1, "untouched"),)

    result = CharacterMemoryEngine().run(storyboard, prompts, _memory())

    assert result.prompts[0].prompt == "untouched"
    assert not result.scores.scores


def test_the_previous_appearance_is_fed_forward() -> None:
    prompts = tuple(_prompt(i, f"base {i}") for i in (1, 2, 3))

    result = CharacterMemoryEngine().run(_storyboard(), prompts, _memory())

    # shot 3 is lin_tian again, so it is told what shot 1 established
    assert "no earlier image" in result.prompts[0].prompt
    assert "long black hair" in result.prompts[2].prompt


def test_the_engine_is_deterministic() -> None:
    prompts = tuple(_prompt(i, f"base {i}") for i in (1, 2, 3))

    first = CharacterMemoryEngine().run(_storyboard(), prompts, _memory())
    second = CharacterMemoryEngine().run(_storyboard(), prompts, _memory())

    assert [p.prompt for p in first.prompts] == [p.prompt for p in second.prompts]


def test_running_without_prompts_is_rejected_with_guidance() -> None:
    with pytest.raises(CharacterMemoryError, match="run `continuity`"):
        CharacterMemoryEngine().run(_storyboard(), (), _memory())
