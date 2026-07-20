"""Visual continuity value objects (domain layer).

The three documents that make consecutive images look like frames of one film:

- a **character bible** — who appears, and what never changes about them;
- a **world bible** — the palette, light, weather and art direction they live in;
- a **visual context** per shot — what came before, what comes next, and what
  must carry across the cut.

Pure and immutable (docs/ai-tool.md §2.1) — no I/O, no vendor SDKs.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CharacterBibleEntry(BaseModel):
    """One character's permanent, never-varying description."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    name: str = ""
    appearance: str = ""
    wardrobe: str = ""
    signature_props: str = ""
    palette: str = ""
    negative_prompt: str = ""

    @property
    def identity(self) -> str:
        """The single line that pins this character's look."""
        parts = [self.appearance, self.wardrobe, self.signature_props]
        return ", ".join(part for part in parts if part)


class CharacterBible(BaseModel):
    """Every character, each described exactly once."""

    model_config = ConfigDict(frozen=True)

    characters: tuple[CharacterBibleEntry, ...] = ()

    def get(self, character_id: str) -> CharacterBibleEntry | None:
        """The entry for ``character_id``, if the bible holds one."""
        key = character_id.strip().lower()
        return next((entry for entry in self.characters if entry.id.lower() == key), None)


class LocationEntry(BaseModel):
    """One place, and how it always looks."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    name: str = ""
    description: str = ""
    lighting: str = ""
    weather: str = ""
    props: str = ""


class WorldBible(BaseModel):
    """The film's fixed visual language: palette, light, era, art direction."""

    model_config = ConfigDict(frozen=True)

    title: str = ""
    genre: str = ""
    style: str = ""
    era: str = ""
    palette: str = ""
    lighting: str = ""
    weather: str = ""
    art_direction: str = ""
    cinematic_style: str = ""
    motifs: str = ""
    negative_prompt: str = ""
    locations: tuple[LocationEntry, ...] = ()

    def location(self, location_id: str) -> LocationEntry | None:
        """The entry for ``location_id``, if the bible holds one."""
        key = location_id.strip().lower()
        return next((entry for entry in self.locations if entry.id.lower() == key), None)


class ShotSummary(BaseModel):
    """A neighbouring shot, compressed to what continuity needs from it."""

    model_config = ConfigDict(frozen=True)

    shot_id: int = Field(default=0, ge=0)
    scene_id: int = Field(default=0, ge=0)
    camera: str = ""
    action: str = ""
    expression: str = ""
    lighting: str = ""
    environment: str = ""

    @property
    def exists(self) -> bool:
        """Whether there actually is such a neighbour."""
        return self.shot_id > 0


class VisualContext(BaseModel):
    """Everything one shot must know about its neighbours to match them."""

    model_config = ConfigDict(frozen=True)

    shot_id: int = Field(ge=1)
    scene_id: int = Field(ge=1)
    previous_shot: ShotSummary = Field(default_factory=ShotSummary)
    current_shot: ShotSummary = Field(default_factory=ShotSummary)
    next_shot: ShotSummary = Field(default_factory=ShotSummary)
    scene_goal: str = ""
    character_state: str = ""
    emotion: str = ""
    camera_continuity: str = ""
    lighting_continuity: str = ""
    color_continuity: str = ""
    weather_continuity: str = ""
    prop_continuity: str = ""
    environment_continuity: str = ""

    @property
    def is_scene_opening(self) -> bool:
        """Whether this shot opens its scene (nothing to match backwards)."""
        return not self.previous_shot.exists or self.previous_shot.scene_id != self.scene_id


class VisualContextDocument(BaseModel):
    """The per-shot continuity contexts for a whole storyboard."""

    model_config = ConfigDict(frozen=True)

    title: str = ""
    shots: tuple[VisualContext, ...] = ()


class PromptScore(BaseModel):
    """How well one prompt carries continuity, per dimension."""

    model_config = ConfigDict(frozen=True)

    shot_id: int = Field(ge=1)
    character_consistency: int = Field(default=0, ge=0, le=100)
    environment_consistency: int = Field(default=0, ge=0, le=100)
    style_consistency: int = Field(default=0, ge=0, le=100)
    story_continuity: int = Field(default=0, ge=0, le=100)
    camera_continuity: int = Field(default=0, ge=0, le=100)
    attempts: int = Field(default=1, ge=1)
    issues: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        """The mean of the five dimensions."""
        return round(
            (
                self.character_consistency
                + self.environment_consistency
                + self.style_consistency
                + self.story_continuity
                + self.camera_continuity
            )
            / 5
        )

    def passed(self, threshold: int) -> bool:
        """Whether the prompt clears ``threshold``."""
        return self.total >= threshold


class PromptScoreDocument(BaseModel):
    """Every prompt's score, plus how the run went overall."""

    model_config = ConfigDict(frozen=True)

    threshold: int = Field(default=90, ge=0, le=100)
    scores: tuple[PromptScore, ...] = ()

    @property
    def average(self) -> int:
        """Mean total across every scored prompt."""
        if not self.scores:
            return 0
        return round(sum(score.total for score in self.scores) / len(self.scores))

    @property
    def failing(self) -> tuple[PromptScore, ...]:
        """The prompts that never reached the threshold."""
        return tuple(score for score in self.scores if not score.passed(self.threshold))
