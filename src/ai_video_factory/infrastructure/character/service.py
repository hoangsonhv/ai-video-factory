"""Build a :class:`CharacterLibrary` from a movie bible.

Deterministic and offline — no AI provider is involved. The same ``movie.json``
always yields byte-identical ``character_library.json``, which is what makes a
character render the same way across scenes and across runs.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Sequence

from ai_video_factory.domain.value_objects.character_library import (
    CharacterLibrary,
    CharacterProfile,
    NormalizedAppearance,
    NormalizedOutfit,
)
from ai_video_factory.domain.value_objects.movie import Appearance, Character, Movie
from ai_video_factory.infrastructure.character.errors import CharacterLibraryError

SEED_MODULO = 2**31
"""Upper bound for generated seeds (fits every image backend's signed range)."""

BASE_NEGATIVE_TERMS: tuple[str, ...] = (
    "inconsistent face",
    "different hairstyle",
    "changing outfit",
    "different age",
    "deformed hands",
    "extra fingers",
    "blurry",
    "low quality",
    "watermark",
    "text",
)
"""Terms every character rejects; a character's own terms are appended."""

CONSISTENCY_SUFFIX = "consistent character design, identical face and outfit in every scene"

_WHITESPACE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    """Collapse whitespace, drop trailing punctuation and lowercase ``value``.

    Applied to appearance and outfit traits only, so two spellings of the same
    trait ("Long  black hair." / "long black hair") compare and render equal.
    Names and dialogue are never normalized.
    """
    return _WHITESPACE.sub(" ", value).strip().strip(".,;:").strip().lower()


def normalize_appearance(character: Character) -> NormalizedAppearance:
    """Normalize the physical traits of ``character`` (clothing excluded)."""
    return NormalizedAppearance(
        hair=normalize_text(character.appearance.hair),
        eyes=normalize_text(character.appearance.eyes),
        face=normalize_text(character.appearance.face),
        body=normalize_text(character.appearance.body),
    )


def normalize_outfit(character: Character) -> NormalizedOutfit:
    """Normalize the wardrobe traits of ``character``."""
    return NormalizedOutfit(
        clothes=normalize_text(character.appearance.clothes),
        accessories=normalize_text(character.appearance.accessories),
    )


def generate_seed(character_id: str) -> int:
    """Derive a stable seed from ``character_id`` (same id → same seed)."""
    digest = hashlib.sha256(character_id.strip().lower().encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % SEED_MODULO


def _split_terms(value: str) -> list[str]:
    return [term.strip().lower() for term in value.split(",") if term.strip()]


def _join_unique(terms: Iterable[str]) -> str:
    unique: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if term and term not in seen:
            seen.add(term)
            unique.append(term)
    return ", ".join(unique)


def generate_negative_prompt(character: Character) -> str:
    """Combine the shared consistency negatives with the character's own."""
    return _join_unique([*BASE_NEGATIVE_TERMS, *_split_terms(character.negative_prompt)])


def generate_master_prompt(
    character: Character,
    appearance: NormalizedAppearance,
    outfit: NormalizedOutfit,
) -> str:
    """Render the single, permanent description of ``character``.

    Trait order is fixed so the prompt is reproducible; empty traits are simply
    omitted rather than emitted as blanks.
    """
    parts: list[str] = [character.name.strip()]
    if character.gender.strip():
        parts.append(normalize_text(character.gender))
    if character.age > 0:
        parts.append(f"{character.age} years old")
    parts.extend(trait for trait in (appearance.hair, appearance.eyes) if trait)
    parts.extend(trait for trait in (appearance.face, appearance.body) if trait)
    if outfit.clothes:
        parts.append(f"wearing {outfit.clothes}")
    if outfit.accessories:
        parts.append(outfit.accessories)
    parts.append(CONSISTENCY_SUFFIX)
    return ", ".join(parts)


def _identity_key(character: Character) -> str:
    """The key two records must share to be the *same* character."""
    return normalize_text(character.id) or normalize_text(character.name)


def _merge(first: Character, later: Character) -> Character:
    """Fill only the traits the first record left empty — never overwrite.

    The first occurrence owns the character's appearance (ADR-025); a duplicate
    may contribute detail the first mention omitted, and its negative terms.
    """
    appearance = first.appearance.model_copy(
        update={
            field: getattr(later.appearance, field)
            for field in Appearance.model_fields
            if not getattr(first.appearance, field).strip()
            and getattr(later.appearance, field).strip()
        }
    )
    negatives = _join_unique(
        [*_split_terms(first.negative_prompt), *_split_terms(later.negative_prompt)]
    )
    return first.model_copy(
        update={
            "appearance": appearance,
            "gender": first.gender or later.gender,
            "age": first.age or later.age,
            "personality": first.personality or later.personality,
            "voice": first.voice or later.voice,
            "negative_prompt": negatives,
        }
    )


def merge_duplicates(characters: Sequence[Character]) -> list[Character]:
    """Collapse records describing the same character into one.

    Two records are duplicates when their ids (or, lacking an id, their names)
    normalize equal. The first occurrence wins for every populated trait.
    """
    merged: dict[str, Character] = {}
    order: list[str] = []
    for character in characters:
        key = _identity_key(character)
        if not key:
            continue
        if key in merged:
            merged[key] = _merge(merged[key], character)
        else:
            merged[key] = character
            order.append(key)
    return [merged[key] for key in order]


class CharacterConsistencyService:
    """Turn a movie's cast into a library of one profile per character."""

    def build(self, movie: Movie) -> CharacterLibrary:
        """Build the character library for ``movie``.

        Raises:
            CharacterLibraryError: If the movie declares no usable character.
        """
        characters = merge_duplicates(movie.characters)
        if not characters:
            raise CharacterLibraryError("movie declares no characters to build a library from")
        return CharacterLibrary(characters=tuple(self._profile(c) for c in characters))

    def _profile(self, character: Character) -> CharacterProfile:
        appearance = normalize_appearance(character)
        outfit = normalize_outfit(character)
        return CharacterProfile(
            id=character.id,
            master_prompt=generate_master_prompt(character, appearance, outfit),
            negative_prompt=generate_negative_prompt(character),
            seed=generate_seed(character.id),
            reference_image=None,
            appearance=appearance,
            outfit=outfit,
            voice_profile=character.voice,
            version=1,
        )
