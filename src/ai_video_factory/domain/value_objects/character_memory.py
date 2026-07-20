"""Character memory value objects (domain layer).

What a character canonically looks like, remembered across runs. The first
image generated for a character becomes its reference; from then on every
prompt restates the same canonical face, hair, body, clothes, weapon,
expression and palette, so the tenth image of someone matches the first.

``appearance_hash`` fingerprints the canonical fields: if it changes between
runs, the character's look has drifted and every image already rendered is
stale. Pure and immutable (docs/ai-tool.md §2.1) — no I/O, no vendor SDKs.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict, Field

CANONICAL_FIELDS = (
    "canonical_face",
    "canonical_hair",
    "canonical_body",
    "canonical_clothes",
    "canonical_weapon",
    "canonical_expression",
    "canonical_color_palette",
)
"""The fields that define a character's look, and so its hash."""


class CharacterMemory(BaseModel):
    """One character's canonical appearance, frozen once and reused.

    ``gender``, ``age`` and ``style`` are not part of the look itself but the
    validator compares them, so they are remembered alongside it.
    """

    model_config = ConfigDict(frozen=True)

    character_id: str = Field(min_length=1)
    canonical_face: str = ""
    canonical_hair: str = ""
    canonical_body: str = ""
    canonical_clothes: str = ""
    canonical_weapon: str = ""
    canonical_expression: str = ""
    canonical_color_palette: str = ""
    reference_image: str | None = None
    appearance_hash: str = ""
    gender: str = ""
    age: str = ""
    style: str = ""

    @property
    def has_reference(self) -> bool:
        """Whether a canonical image has been adopted yet."""
        return bool(self.reference_image)

    @property
    def summary(self) -> str:
        """The one-line appearance summary a prompt must restate."""
        parts = (
            self.canonical_face,
            self.canonical_hair,
            self.canonical_body,
            self.canonical_clothes,
            self.canonical_weapon,
            self.canonical_color_palette,
        )
        return ", ".join(part for part in parts if part)

    def compute_hash(self) -> str:
        """Fingerprint the canonical fields, so drift is detectable."""
        material = "|".join(getattr(self, field) for field in CANONICAL_FIELDS)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]

    @property
    def is_drifted(self) -> bool:
        """Whether the stored hash no longer matches the stored appearance."""
        return bool(self.appearance_hash) and self.appearance_hash != self.compute_hash()


class CharacterMemoryDocument(BaseModel):
    """Every character the film remembers."""

    model_config = ConfigDict(frozen=True)

    characters: tuple[CharacterMemory, ...] = ()

    def get(self, character_id: str) -> CharacterMemory | None:
        """The memory for ``character_id``, if one is held."""
        key = character_id.strip().lower()
        return next((c for c in self.characters if c.character_id.lower() == key), None)

    @property
    def with_references(self) -> tuple[CharacterMemory, ...]:
        """The characters that have adopted a canonical image."""
        return tuple(c for c in self.characters if c.has_reference)


class AppearanceScore(BaseModel):
    """How closely one prompt restates a character's canonical appearance."""

    model_config = ConfigDict(frozen=True)

    shot_id: int = Field(ge=1)
    scene_id: int = Field(default=0, ge=0)
    character_id: str = ""
    hair: int = Field(default=0, ge=0, le=100)
    face: int = Field(default=0, ge=0, le=100)
    clothes: int = Field(default=0, ge=0, le=100)
    weapon: int = Field(default=0, ge=0, le=100)
    colors: int = Field(default=0, ge=0, le=100)
    gender: int = Field(default=0, ge=0, le=100)
    age: int = Field(default=0, ge=0, le=100)
    style: int = Field(default=0, ge=0, le=100)
    attempts: int = Field(default=1, ge=1)
    issues: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        """The mean of the eight compared attributes."""
        values = (
            self.hair,
            self.face,
            self.clothes,
            self.weapon,
            self.colors,
            self.gender,
            self.age,
            self.style,
        )
        return round(sum(values) / len(values))

    def passed(self, threshold: int) -> bool:
        """Whether the prompt clears ``threshold``."""
        return self.total >= threshold


class AppearanceScoreDocument(BaseModel):
    """Every prompt's appearance score for a run."""

    model_config = ConfigDict(frozen=True)

    threshold: int = Field(default=90, ge=0, le=100)
    scores: tuple[AppearanceScore, ...] = ()

    @property
    def average(self) -> int:
        """Mean total across every scored prompt."""
        if not self.scores:
            return 0
        return round(sum(score.total for score in self.scores) / len(self.scores))

    @property
    def failing(self) -> tuple[AppearanceScore, ...]:
        """The prompts that never reached the threshold."""
        return tuple(score for score in self.scores if not score.passed(self.threshold))
