"""Derive what must be visible at each depth of the frame (pure, no I/O).

An image model given only a character and a mood draws a character on a
backdrop. Naming a foreground, a midground and a background is what turns that
into a place the character is standing in — so this is the single most direct
lever on the sprint's "environment must be visible" acceptance.

Every depth is derived from text the story already carries: the shot's own
environment line, the scene's location, the world bible's entry for that
location, and the shot's lighting. Nothing is invented; a depth with no source
is left empty, and a shot with **all three** empty is rejected rather than
quietly rendered as a portrait.
"""

from __future__ import annotations

from ai_video_factory.domain.value_objects.continuity import WorldBible
from ai_video_factory.domain.value_objects.movie import Scene
from ai_video_factory.domain.value_objects.shot_plan import EnvironmentVisibility, ShotType
from ai_video_factory.domain.value_objects.storyboard import StoryboardShot

# Weather and atmosphere read as foreground: they sit between lens and subject.
_ATMOSPHERE_WORDS: tuple[str, ...] = (
    "fog",
    "mist",
    "rain",
    "snow",
    "smoke",
    "dust",
    "ember",
    "spark",
    "steam",
    "haze",
    "petal",
    "leaves",
)


def _clean(value: str) -> str:
    return " ".join(value.split()).strip().strip(",;.").strip()


def _first_clause(value: str) -> str:
    """The leading clause of a description, which names the place itself."""
    cleaned = _clean(value)
    for separator in (", with", " with ", ", and", ". ", ", "):
        if separator in cleaned:
            return _clean(cleaned.split(separator, 1)[0])
    return cleaned


def _atmosphere(text: str) -> str:
    """Any weather or airborne element the text names, as a foreground layer."""
    lowered = text.lower()
    found = [word for word in _ATMOSPHERE_WORDS if word in lowered]
    if not found:
        return ""
    # Return the clause that mentions it, so the phrasing stays the story's own.
    for clause in _clean(text).replace(";", ",").split(","):
        if any(word in clause.lower() for word in found):
            return _clean(clause)
    return ""


def build_environment(
    shot: StoryboardShot,
    scene: Scene | None,
    world: WorldBible,
    shot_type: ShotType,
) -> EnvironmentVisibility:
    """Name what must read at each depth of this frame.

    The background is the place; the midground is what surrounds the action;
    the foreground is whatever sits nearest the lens — atmosphere, practical
    lighting, or the props the location is known for.
    """
    location = world.location(scene.location) if scene and scene.location else None
    location_text = _clean(location.description if location else "")
    scene_location = _clean(scene.location.replace("_", " ")) if scene else ""
    environment = _clean(shot.environment)

    background = _first_clause(location_text) or scene_location
    midground = environment or _clean(location.props if location else "")
    foreground = (
        _atmosphere(environment)
        or _atmosphere(location_text)
        or _clean(location.weather if location else "")
        or _clean(world.weather)
        or _clean(shot.lighting)
    )

    # A close size legitimately loses the deep background, but must keep
    # something behind the subject — that is what stops it being a headshot on
    # a void. The midground carries it when the background is thin.
    if shot_type in (ShotType.CLOSE_UP, ShotType.EXTREME_CLOSE) and not background:
        background = midground or scene_location

    # The foreground and midground must not be the same sentence twice.
    if foreground and foreground.lower() == midground.lower():
        foreground = _clean(shot.lighting) if _clean(shot.lighting) != midground else ""

    return EnvironmentVisibility(
        foreground=foreground,
        midground=midground,
        background=background,
    )
