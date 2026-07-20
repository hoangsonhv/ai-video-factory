"""Add remembered identity to a composed prompt (pure, no I/O).

Every prompt after the first image of a character must restate that
character's canonical appearance, cite the reference image, and say what the
previously generated image of them looked like. This module adds those three
sections to a prompt the continuity engine already built.

**Reference handling depends on the provider.** Where a driver accepts an image
reference the path is attached and the prompt says so; where it does not — the
case for every image driver shipped today — the reference is described in words
instead, because a path a provider cannot read helps nobody.

As with the continuity composer, explicitness escalates: level 0 states the
appearance once, level 1 repeats it as an instruction, level 2 pins every
attribute individually.
"""

from __future__ import annotations

from ai_video_factory.domain.value_objects.character_memory import CharacterMemory

SEPARATOR = "\n"
MAX_LEVEL = 2

PROVIDERS_WITH_IMAGE_REFERENCE: frozenset[str] = frozenset()
"""Image drivers that accept a reference image.

Empty today: neither ``pollinations`` nor ``gemini_imagen`` is wired for
image-to-image, and this sprint may not change a provider. A driver that gains
the capability is added here, and the reference is attached instead of
described — no other code changes.
"""


def supports_image_reference(provider: str) -> bool:
    """Whether ``provider`` can be handed a reference image directly."""
    return provider.strip().lower() in PROVIDERS_WITH_IMAGE_REFERENCE


def _clean(value: str) -> str:
    return " ".join(value.split()).strip().strip(",;").strip()


def _section(label: str, value: str) -> str:
    cleaned = _clean(value)
    return f"{label}: {cleaned}" if cleaned else ""


def reference_section(memory: CharacterMemory, provider: str) -> str:
    """Cite the canonical image — attached if the provider reads one, else described."""
    if not memory.has_reference:
        return _section(
            "Reference Image",
            "none adopted yet; this image becomes the canonical reference for "
            f"{memory.character_id}",
        )
    if supports_image_reference(provider):
        return _section("Reference Image", f"{memory.reference_image} (attached)")
    return _section(
        "Reference Image",
        f"match the established look of {memory.character_id} exactly as first "
        f"rendered ({memory.reference_image}): {memory.summary}",
    )


def appearance_section(memory: CharacterMemory, level: int) -> str:
    """The remembered appearance, restated more insistently as level rises."""
    parts = [_section("Appearance Summary", memory.summary)]
    if level >= 1:
        parts.append(
            _section(
                "Identity lock",
                f"{memory.character_id} must be the same person as in every other image: "
                "same face, same hair, same wardrobe, same colours",
            )
        )
    if level >= 2:
        parts.extend(
            [
                _section("Face", memory.canonical_face),
                _section("Hair", memory.canonical_hair),
                _section("Body", memory.canonical_body),
                _section("Clothes", memory.canonical_clothes),
                _section("Weapon", memory.canonical_weapon),
                _section("Colour palette", memory.canonical_color_palette),
                _section("Gender", memory.gender),
                _section("Age", memory.age),
                _section("Style", memory.style),
            ]
        )
    return SEPARATOR.join(part for part in parts if part)


def previous_appearance_section(previous: str) -> str:
    """What the last generated image of this character looked like."""
    return _section(
        "Previous Generated Appearance",
        previous or "no earlier image of this character has been generated",
    )


def enrich_prompt(
    prompt: str,
    memory: CharacterMemory,
    *,
    provider: str = "",
    previous_appearance: str = "",
    level: int = 0,
) -> str:
    """Prepend the remembered identity to an already-composed prompt."""
    sections = [
        reference_section(memory, provider),
        appearance_section(memory, level),
        previous_appearance_section(previous_appearance),
        prompt,
    ]
    return SEPARATOR.join(section for section in sections if section)
