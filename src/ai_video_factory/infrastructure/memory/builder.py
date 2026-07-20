"""Build and update character memory (pure, no I/O).

A character's canonical look is derived once from the character bible, then
**frozen**: later runs reuse the remembered values rather than re-deriving
them, because a look that changes between runs is exactly the drift this stage
exists to stop. Only two things update after the first run — a reference image
being adopted, and fields that were empty gaining a value.

The first image that exists for a character becomes its canonical reference.
Adoption is by *existence*: whichever image the pipeline has produced for that
character is the one every later prompt must match.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ai_video_factory.domain.value_objects.character_memory import (
    CharacterMemory,
    CharacterMemoryDocument,
)
from ai_video_factory.domain.value_objects.continuity import CharacterBible
from ai_video_factory.domain.value_objects.movie import Movie
from ai_video_factory.domain.value_objects.storyboard import Storyboard

WEAPON_WORDS = ("sword", "blade", "spear", "bow", "staff", "dagger", "gun", "axe", "kiếm")
"""Words that mark a prop as a weapon, so it can be pinned separately."""


def _clean(value: str) -> str:
    return " ".join(value.split()).strip().strip(",;").strip()


def _split_weapon(props: str) -> tuple[str, str]:
    """Separate weapon props from the rest, so each can be pinned on its own."""
    weapons: list[str] = []
    others: list[str] = []
    for part in props.split(","):
        cleaned = _clean(part)
        if not cleaned:
            continue
        target = weapons if any(word in cleaned.lower() for word in WEAPON_WORDS) else others
        target.append(cleaned)
    return ", ".join(weapons), ", ".join(others)


def _face_and_hair(appearance: str) -> tuple[str, str]:
    """Split the appearance line into its hair part and everything else."""
    hair: list[str] = []
    face: list[str] = []
    for part in appearance.split(","):
        cleaned = _clean(part)
        if not cleaned:
            continue
        (hair if "hair" in cleaned.lower() else face).append(cleaned)
    return ", ".join(face), ", ".join(hair)


def derive_memory(
    bible: CharacterBible, movie: Movie | None = None, style: str = ""
) -> CharacterMemoryDocument:
    """Derive a first-run memory from the character bible."""
    people = {c.id.strip().lower(): c for c in (movie.characters if movie else ())}

    memories: list[CharacterMemory] = []
    for entry in bible.characters:
        person = people.get(entry.id.strip().lower())
        face, hair = _face_and_hair(entry.appearance)
        weapon, _props = _split_weapon(entry.signature_props)
        memory = CharacterMemory(
            character_id=entry.id,
            canonical_face=face,
            canonical_hair=hair,
            canonical_body=_clean(person.appearance.body) if person else "",
            canonical_clothes=_clean(entry.wardrobe),
            canonical_weapon=weapon,
            canonical_expression=_clean(person.personality) if person else "",
            canonical_color_palette=_clean(entry.palette),
            reference_image=None,
            gender=_clean(person.gender) if person else "",
            age=str(person.age) if person and person.age else "",
            style=_clean(style),
        )
        memories.append(memory.model_copy(update={"appearance_hash": memory.compute_hash()}))
    return CharacterMemoryDocument(characters=tuple(memories))


def merge_memory(
    remembered: CharacterMemoryDocument, derived: CharacterMemoryDocument
) -> CharacterMemoryDocument:
    """Keep what is already remembered; only fill gaps and add newcomers.

    A remembered canonical value is never overwritten by a freshly derived one
    — that is what makes the memory a memory. Empty fields are filled, because
    an absent value pins nothing.
    """
    merged: list[CharacterMemory] = []
    seen: set[str] = set()

    for existing in remembered.characters:
        seen.add(existing.character_id.strip().lower())
        fresh = derived.get(existing.character_id)
        if fresh is None:
            merged.append(existing)
            continue
        gaps = {
            field: getattr(fresh, field)
            for field in CharacterMemory.model_fields
            if field not in {"character_id", "reference_image", "appearance_hash"}
            and not str(getattr(existing, field) or "").strip()
            and str(getattr(fresh, field) or "").strip()
        }
        updated = existing.model_copy(update=gaps) if gaps else existing
        merged.append(
            updated.model_copy(update={"appearance_hash": updated.compute_hash()})
            if gaps
            else updated
        )

    merged.extend(
        memory for memory in derived.characters if memory.character_id.strip().lower() not in seen
    )
    return CharacterMemoryDocument(characters=tuple(merged))


def first_image_for(
    storyboard: Storyboard, character_id: str, images: Mapping[int, Path]
) -> Path | None:
    """The earliest generated image showing ``character_id``.

    Shots are walked in timeline order, so the *first* image the pipeline made
    of a character is the one adopted — later ones must match it, not redefine
    it.
    """
    key = character_id.strip().lower()
    for shot in storyboard.shots:
        names = {part.strip().lower() for part in shot.character.replace(",", " ").split()}
        if key in names and shot.id in images:
            return images[shot.id]
    return None


def adopt_references(
    memory: CharacterMemoryDocument, storyboard: Storyboard, images: Mapping[int, Path]
) -> CharacterMemoryDocument:
    """Adopt a canonical reference image for characters that lack one.

    A reference already adopted is never replaced: re-pointing it at a later
    image would silently redefine the character mid-film.
    """
    adopted: list[CharacterMemory] = []
    for character in memory.characters:
        if character.has_reference:
            adopted.append(character)
            continue
        image = first_image_for(storyboard, character.character_id, images)
        adopted.append(
            character.model_copy(update={"reference_image": str(image)}) if image else character
        )
    return CharacterMemoryDocument(characters=tuple(adopted))
