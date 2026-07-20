"""Compose a shot's ``video_prompt`` (pure, no I/O).

The prompt targets **AI video models**, not image models: it leads with who is
on screen (from the character library, so identity stays fixed), then the
camera setup, then — the part a still-image prompt never carries — what *moves*
during the shot: the subject, their expression, and the environment around
them. It closes with a temporal-coherence directive, because a video model must
hold one identity across every frame rather than compose a single good picture.

The model's own description of the shot is folded in as the action; identity
and the negative prompt come from the library, never from the model, so a shot
can never contradict the character bible (ADR-026).

Empty fields are omitted rather than padded with filler: a blank means "not
specified", and inventing "natural movement" would recreate exactly the generic
prompt this stage exists to replace.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ai_video_factory.domain.value_objects.character_library import CharacterProfile
from ai_video_factory.domain.value_objects.director import Shot
from ai_video_factory.domain.value_objects.movie import Location, Movie, Scene

SEPARATOR = " | "
NEGATIVE_MARKER = "negative:"

VIDEO_DIRECTIVE = (
    "continuous single-take motion, temporally coherent, "
    "consistent character identity in every frame, no morphing, no flicker"
)
"""Appended to every prompt — the difference between a video and a still."""


def _clean(value: str) -> str:
    return " ".join(value.split()).strip().strip(",;").strip()


def _labelled(label: str, value: str) -> str:
    cleaned = _clean(value)
    return f"{label}: {cleaned}" if cleaned else ""


def _join(parts: Iterable[str], separator: str = ", ") -> str:
    return separator.join(part for part in parts if part)


def _unique(terms: Iterable[str]) -> str:
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        cleaned = term.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            unique.append(cleaned)
    return ", ".join(unique)


def _cast(scene: Scene, profiles: Mapping[str, CharacterProfile]) -> list[CharacterProfile]:
    """The library profiles for the characters present in ``scene``."""
    found = (profiles.get(character_id.strip().lower()) for character_id in scene.characters)
    return [profile for profile in found if profile is not None]


def _setting(scene: Scene, locations: Mapping[str, Location]) -> str:
    location = locations.get(scene.location.strip().lower())
    if location is None:
        return ""
    return _join([location.name, location.description])


def build_shot_prompt(
    movie: Movie,
    scene: Scene,
    shot: Shot,
    profiles: Mapping[str, CharacterProfile],
    locations: Mapping[str, Location],
) -> str:
    """Compose the video-model prompt for one shot.

    Combines the character library (identity), the shot's camera setup, its
    motion and expression, the environment, and the scene's setting.
    """
    cast = _cast(scene, profiles)

    camera = _join([shot.camera, shot.camera_motion, shot.lens, shot.framing])
    motion = _join(
        [
            _labelled("subject", shot.subject),
            _labelled("action", shot.action),
            _labelled("expression", shot.expression),
        ]
    )

    sections = [
        _unique(profile.master_prompt for profile in cast),
        _labelled("Shot", camera),
        # The model's own description of the shot, folded in as the beat.
        _clean(shot.video_prompt),
        _labelled("Motion", motion),
        _labelled("Environment", shot.environment_motion),
        _labelled("Lighting", shot.lighting),
        _labelled("Mood", scene.emotion),
        _labelled("Setting", _setting(scene, locations)),
        _labelled("Style", movie.style),
        _labelled("Duration", f"{shot.duration}s"),
        _labelled("Transition", shot.transition),
        VIDEO_DIRECTIVE,
    ]

    negatives = _unique(term for profile in cast for term in profile.negative_prompt.split(","))
    if negatives:
        sections.append(f"{NEGATIVE_MARKER} {negatives}")

    return SEPARATOR.join(section for section in sections if section)
