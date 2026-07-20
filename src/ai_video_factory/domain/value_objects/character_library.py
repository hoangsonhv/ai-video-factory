"""Character library value objects (domain layer).

The *character consistency* contract: one immutable profile per character,
carrying the single ``master_prompt`` that every scene must reuse instead of
re-describing the character. Pure and immutable (docs/ai-tool.md §2.1) — no
I/O, no vendor SDKs. This is the schema of ``output/character_library.json``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class NormalizedAppearance(BaseModel):
    """A character's normalized, permanent physical appearance."""

    model_config = ConfigDict(frozen=True)

    hair: str = ""
    eyes: str = ""
    face: str = ""
    body: str = ""


class NormalizedOutfit(BaseModel):
    """A character's normalized, permanent outfit."""

    model_config = ConfigDict(frozen=True)

    clothes: str = ""
    accessories: str = ""


class CharacterProfile(BaseModel):
    """The consistency profile of one character.

    ``master_prompt`` is the *only* description a scene may use for this
    character; ``seed`` is deterministic so the same character renders the
    same way on every run.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    master_prompt: str = ""
    negative_prompt: str = ""
    seed: int = Field(default=0, ge=0)
    reference_image: str | None = None
    appearance: NormalizedAppearance = Field(default_factory=NormalizedAppearance)
    outfit: NormalizedOutfit = Field(default_factory=NormalizedOutfit)
    voice_profile: str = ""
    version: int = Field(default=1, ge=1)


class CharacterLibrary(BaseModel):
    """Every character of a movie, each appearing exactly once."""

    model_config = ConfigDict(frozen=True)

    characters: tuple[CharacterProfile, ...] = ()
