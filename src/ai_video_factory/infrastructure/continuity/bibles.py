"""Derive the character and world bibles from existing artifacts (pure, no I/O).

Neither bible is authored by a model: the character bible is a restatement of
the character library (ADR-026), and the world bible is assembled from the
movie's style, genre and locations. Deriving rather than generating keeps both
reproducible and free — and once written out they are ordinary JSON an operator
can hand-tune, which is where richer art direction belongs.

Only what the sources actually say is carried across. Where a source is silent
the field stays empty rather than being filled with invented detail; an empty
field is visible in the prompt score, invented detail is not.
"""

from __future__ import annotations

from collections.abc import Iterable

from ai_video_factory.domain.value_objects.character_library import CharacterLibrary
from ai_video_factory.domain.value_objects.continuity import (
    CharacterBible,
    CharacterBibleEntry,
    LocationEntry,
    WorldBible,
)
from ai_video_factory.domain.value_objects.movie import Movie

DEFAULT_NEGATIVE = (
    "inconsistent face, different hairstyle, changing outfit, different age, "
    "deformed hands, extra fingers, blurry, low quality, watermark, text"
)
"""Applied film-wide; a character's own negatives are added on top."""


def _clean(value: str) -> str:
    return " ".join(value.split()).strip().strip(",;").strip()


def _join(parts: Iterable[str]) -> str:
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        cleaned = _clean(part)
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            unique.append(cleaned)
    return ", ".join(unique)


def build_character_bible(library: CharacterLibrary, movie: Movie | None = None) -> CharacterBible:
    """Restate the character library as a bible.

    The library already fixes each character's look (ADR-026); this splits it
    into the parts a prompt needs to name separately — the face and body that
    never change, the wardrobe, and the props that identify them.
    """
    movie_characters = {c.id.strip().lower(): c for c in (movie.characters if movie else ())}

    entries: list[CharacterBibleEntry] = []
    for profile in library.characters:
        source = movie_characters.get(profile.id.strip().lower())
        appearance = _join(
            [
                profile.appearance.hair,
                profile.appearance.eyes,
                profile.appearance.face,
                profile.appearance.body,
            ]
        )
        entries.append(
            CharacterBibleEntry(
                id=profile.id,
                name=source.name if source else profile.id,
                appearance=appearance or _clean(profile.master_prompt),
                wardrobe=_clean(profile.outfit.clothes),
                signature_props=_clean(profile.outfit.accessories),
                palette=_join([profile.appearance.hair, profile.outfit.clothes]),
                negative_prompt=_clean(profile.negative_prompt) or DEFAULT_NEGATIVE,
            )
        )
    return CharacterBible(characters=tuple(entries))


def build_world_bible(movie: Movie) -> WorldBible:
    """Assemble the film's visual language from the movie bible.

    Palette, lighting and weather are read out of the location descriptions
    the Movie Builder already wrote; the style and genre set the art direction.
    Nothing here is invented — a thin world bible is an honest signal that the
    upstream descriptions were thin.
    """
    locations = tuple(
        LocationEntry(
            id=location.id,
            name=location.name,
            description=_clean(location.description),
            lighting=_clean(location.description),
            weather="",
            props="",
        )
        for location in movie.locations
    )
    setting = _join([location.description for location in movie.locations])
    return WorldBible(
        title=movie.title,
        genre=_clean(movie.genre),
        style=_clean(movie.style),
        era="",
        palette=setting,
        lighting=setting,
        weather="",
        art_direction=_join([movie.style, movie.genre]),
        cinematic_style=_join([movie.style, "cinematic film still", "consistent colour grade"]),
        motifs="",
        negative_prompt=DEFAULT_NEGATIVE,
        locations=locations,
    )
