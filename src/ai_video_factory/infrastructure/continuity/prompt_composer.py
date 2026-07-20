"""The prompt builder — the single place an image prompt is written.

Every stage that needs an image prompt calls :func:`build_prompt`. There is one
builder, not one per stage: the same eight sections, in the same order, from the
same sources, whoever is asking.

**Section order is fixed** — Character, Action, Environment, Camera, Lighting,
Composition, Style, Negative Prompt — because order is what an image model
weights. A prompt that opens on a face produces a face.

**Provenance is fixed too.** Each section has one owner:

===============  ==========================================================
Character        ``character_bible.json`` — never the storyboard, never the
                 shot's own text, so a character cannot be re-described
                 differently in two frames.
Action           the storyboard shot, reduced to **one** primary action.
Environment      ``world_bible.json`` for the place and its art direction,
                 plus the shot's own line for what is happening in the frame
                 right now — otherwise every shot in a location reads alike.
Camera           the shot's framing decision (size, distance, angle, lens).
===============  ==========================================================

Four rules are enforced rather than hoped for:

- **no portrait-only prompts** — a frame that is not a close size says so in
  its own negatives, and close-up language leaking in from upstream text is
  stripped;
- **one primary action** — a shot renders one beat, so only the first is kept;
- **no duplicated fragments** — de-duplication is term-by-term across the
  *whole* prompt, not within a section;
- **no empty superlatives** — "masterpiece", "8k" and friends are removed
  unless a caller explicitly asks for them.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from pydantic import BaseModel, ConfigDict

from ai_video_factory.domain.value_objects.continuity import CharacterBible, WorldBible

SEPARATOR = "\n"
NEGATIVE_LABEL = "Negative Prompt:"

MAX_WORDS = 350
"""A prompt past this length stops being read by the model, not by us."""

SECTION_ORDER: tuple[str, ...] = (
    "Character",
    "Action",
    "Environment",
    "Camera",
    "Lighting",
    "Composition",
    "Style",
    NEGATIVE_LABEL[:-1],
)
"""The eight sections, in the order they are written."""

BANNED_FRAMING: tuple[str, ...] = (
    "close-up",
    "close up",
    "closeup",
    "portrait",
    "headshot",
    "head shot",
    "face focus",
    "facial focus",
    "focus on the face",
    "focus on his face",
    "focus on her face",
)
"""Framing language that produces a portrait regardless of everything else."""

EMPTY_SUPERLATIVES: tuple[str, ...] = (
    "masterpiece",
    "best quality",
    "high quality",
    "highest quality",
    "8k",
    "4k",
    "award winning",
    "award-winning",
    "ultra detailed",
    "ultra-detailed",
    "hyper detailed",
    "trending on artstation",
)
"""Words that describe no image. They cost tokens and buy nothing."""

ANTI_PORTRAIT_NEGATIVES: str = (
    "portrait, headshot, close-up framing, face filling the frame, "
    "cropped at the shoulders, blank background, studio backdrop, "
    "empty background, isolated subject"
)
"""What a shot that is not close must explicitly refuse."""

BASE_NEGATIVES: str = (
    "different face between shots, changed outfit, mismatched lighting, inconsistent colour grade"
)

# " and ", ", then ", "; " and " while " each start a second beat.
_ACTION_SPLIT = re.compile(r"\s*(?:,\s*then\s+|\s+then\s+|\s+and\s+|;\s*|\s+while\s+)", re.I)


class PromptSource(BaseModel):
    """What the builder needs about one shot, whoever is asking for it.

    Every stage adapts its own model into this, so the builder never learns
    about a shot plan, a visual context or a cinematic direction — and adding a
    ninth caller does not mean a ninth builder.
    """

    model_config = ConfigDict(frozen=True)

    character_id: str = ""
    action: str = ""
    environment: str = ""
    camera: str = ""
    lighting: str = ""
    composition: str = ""
    allows_close_framing: bool = False
    """Whether a close size was actually chosen for this shot."""


def _clean(value: str) -> str:
    return " ".join(value.split()).strip().strip(",;.").strip()


def _terms(value: str) -> list[str]:
    return [term for term in (_clean(part) for part in value.split(",")) if term]


def primary_action(action: str) -> str:
    """The first beat of an action, and only the first.

    A shot is one continuous setup, so "draws a sword and turns" asks a still
    image for two moments at once. Keeping the first is what makes the frame
    renderable.
    """
    cleaned = _clean(action)
    if not cleaned:
        return ""
    return _clean(_ACTION_SPLIT.split(cleaned, maxsplit=1)[0])


def strip_framing(text: str, *, allowed: bool) -> str:
    """Remove close-up language a shot was not planned for.

    The words come from upstream text an LLM wrote, not from us. Removing the
    phrase beats refusing the shot: the writer's meaning survives and the
    framing decision stays with whoever made it.
    """
    if allowed:
        return text
    cleaned = text
    for phrase in BANNED_FRAMING:
        while phrase in cleaned.lower():
            start = cleaned.lower().index(phrase)
            cleaned = cleaned[:start] + cleaned[start + len(phrase) :]
    return _clean(cleaned)


def strip_superlatives(text: str, *, allowed: bool) -> str:
    """Remove words that describe no image."""
    if allowed:
        return text
    kept = [
        term
        for term in _terms(text)
        if term.lower() not in EMPTY_SUPERLATIVES
        and not any(word == term.lower() for word in EMPTY_SUPERLATIVES)
    ]
    return ", ".join(kept)


def positive_part(prompt: str) -> str:
    """The prompt without its negative section.

    A guard must read only this: the negative section deliberately *contains*
    the banned words — that is how it refuses them — so scanning the whole
    prompt would flag every protected shot for its own protection.
    """
    head, _, _ = prompt.partition(NEGATIVE_LABEL)
    return head


def find_violations(prompt: str, *, allowed: bool) -> tuple[str, ...]:
    """Every banned framing phrase the prompt's positive half still carries."""
    if allowed:
        return ()
    lowered = positive_part(prompt).lower()
    return tuple(phrase for phrase in BANNED_FRAMING if phrase in lowered)


def word_count(prompt: str) -> int:
    """How many words the prompt spends."""
    return len(prompt.split())


class _Deduplicator:
    """Keeps the first occurrence of each term across the whole prompt.

    Per-section de-duplication is not enough: the same boilerplate arrives from
    the world bible, every character's negatives and the art direction, so a
    term has to be remembered across sections to be removed.
    """

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def take(self, parts: Iterable[str]) -> str:
        kept: list[str] = []
        for part in parts:
            for term in _terms(part):
                key = term.lower()
                if key not in self._seen:
                    self._seen.add(key)
                    kept.append(term)
        return ", ".join(kept)


def _character(source: PromptSource, bible: CharacterBible, dedupe: _Deduplicator) -> str:
    """Who is in frame — from the character bible, and nowhere else."""
    entry = bible.get(source.character_id) if source.character_id else None
    if entry is None:
        return dedupe.take([_clean(source.character_id.replace("_", " "))])
    return dedupe.take([entry.name, entry.identity])


def _environment(source: PromptSource, world: WorldBible, dedupe: _Deduplicator) -> str:
    """Where it happens — the world bible's place, plus this frame's own detail."""
    # No palette here: a palette is a style attribute, and this bible's palette
    # field holds every location's description, which would drown the one
    # location the shot is actually in.
    return dedupe.take(
        [source.environment, world.title, world.era, world.art_direction, world.cinematic_style]
    )


def _style(world: WorldBible, extra: Sequence[str], dedupe: _Deduplicator) -> str:
    """The film's look — style, genre and palette, plus anything configured."""
    return dedupe.take([world.style, world.genre, world.palette, *extra])


def _negatives(
    source: PromptSource, bible: CharacterBible, world: WorldBible, dedupe: _Deduplicator
) -> str:
    parts: list[str] = []
    if not source.allows_close_framing:
        parts.append(ANTI_PORTRAIT_NEGATIVES)
    parts.extend([world.negative_prompt, *(entry.negative_prompt for entry in bible.characters)])
    parts.append(BASE_NEGATIVES)
    return dedupe.take(parts)


def _fit(sections: list[tuple[str, str]], budget: int) -> list[tuple[str, str]]:
    """Trim to the word budget, sacrificing the least load-bearing text first.

    The negative prompt goes first because it is the longest and the most
    repetitive; the environment's trailing detail goes next. The eight section
    labels themselves are never dropped, so a trimmed prompt is still a
    complete prompt.
    """
    order_of_sacrifice = (NEGATIVE_LABEL[:-1], "Environment", "Style")
    trimmed = dict(sections)
    for label in order_of_sacrifice:
        rendered = _render(list(trimmed.items()))
        if word_count(rendered) <= budget:
            break
        terms = _terms(trimmed.get(label, ""))
        while terms and word_count(_render(list(trimmed.items()))) > budget:
            terms.pop()
            trimmed[label] = ", ".join(terms)
    return [(label, trimmed[label]) for label, _ in sections]


def _render(sections: Sequence[tuple[str, str]]) -> str:
    return SEPARATOR.join(f"{label}: {value}" for label, value in sections if value)


def build_prompt(
    source: PromptSource,
    bible: CharacterBible,
    world: WorldBible,
    *,
    style_words: Sequence[str] = (),
    allow_superlatives: bool = False,
    max_words: int = MAX_WORDS,
) -> str:
    """Write one shot's image prompt.

    Eight sections in a fixed order, each from its own source, de-duplicated
    across the whole prompt and trimmed to ``max_words``.

    ``style_words`` are the only way superlatives enter, and only when
    ``allow_superlatives`` is set — that is what "unless explicitly configured"
    means.
    """
    close = source.allows_close_framing
    dedupe = _Deduplicator()

    # De-duplication runs in *claim* order, not output order. Environment is the
    # catch-all — it draws on the art direction, palette and era — so it claims
    # last among the positive sections. Letting it go first lets it swallow the
    # one word Style needed (both say "cinematic"), emptying a required section.
    character = _character(source, bible, dedupe)
    style = _style(world, style_words, dedupe)
    environment = _environment(source, world, dedupe)
    negatives = _negatives(source, bible, world, dedupe)

    sections: list[tuple[str, str]] = [
        ("Character", character),
        ("Action", strip_framing(primary_action(source.action), allowed=close)),
        ("Environment", strip_framing(environment, allowed=close)),
        ("Camera", strip_framing(_clean(source.camera), allowed=close)),
        ("Lighting", _clean(source.lighting)),
        ("Composition", _clean(source.composition)),
        ("Style", style),
        (NEGATIVE_LABEL[:-1], negatives),
    ]

    if not allow_superlatives:
        negatives_label = NEGATIVE_LABEL[:-1]
        sections = [
            # The negatives may legitimately name a superlative in order to
            # refuse it; only the positive half is filtered.
            (label, value if label == negatives_label else strip_superlatives(value, allowed=False))
            for label, value in sections
        ]

    return _render(_fit(sections, max_words))
