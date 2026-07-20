"""Flatten a directed movie onto a timeline (pure, no I/O, no provider calls).

Every shot of every scene is laid end to end in order, giving each an absolute
``speech_start``/``speech_end``. The narration is then mapped **onto** that
timeline: a shot's subtitle is whatever the narrator says while it is on
screen, and its ``audio_segment`` is the matching slice of the narration track.

Shot durations are never rewritten to chase the narration — they come from the
director and stay put. Where the two lengths disagree the storyboard reports
the drift rather than silently stretching shots out of their permitted range.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from ai_video_factory.domain.value_objects.character_library import CharacterProfile
from ai_video_factory.domain.value_objects.director import DirectedMovie, DirectedScene, Shot
from ai_video_factory.domain.value_objects.movie import Location
from ai_video_factory.domain.value_objects.storyboard import (
    AudioSegment,
    Storyboard,
    StoryboardShot,
)
from ai_video_factory.infrastructure.storyboard.errors import StoryboardError
from ai_video_factory.infrastructure.storyboard.narration import NarrationCue, narration_span

SEPARATOR = " | "
STILL_DIRECTIVE = "single frame, sharp focus, cinematic composition"
"""Closes the image prompt — this one describes a still, not motion."""


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


def _cast(scene: DirectedScene, profiles: Mapping[str, CharacterProfile]) -> list[CharacterProfile]:
    found = (profiles.get(character_id.strip().lower()) for character_id in scene.characters)
    return [profile for profile in found if profile is not None]


def _setting(scene: DirectedScene, locations: Mapping[str, Location]) -> str:
    location = locations.get(scene.location.strip().lower())
    return _join([location.name, location.description]) if location else ""


def build_image_prompt(
    movie: DirectedMovie,
    scene: DirectedScene,
    shot: Shot,
    profiles: Mapping[str, CharacterProfile],
    locations: Mapping[str, Location],
) -> str:
    """Compose the still-frame prompt for a shot's key frame.

    The same identity and framing as the video prompt, minus the motion — this
    describes one frame, so it names no movement.
    """
    cast = _cast(scene, profiles)
    sections = [
        _unique(profile.master_prompt for profile in cast),
        _labelled("Shot", _join([shot.camera, shot.lens, shot.framing])),
        _labelled("Pose", shot.action),
        _labelled("Expression", shot.expression),
        _labelled("Lighting", shot.lighting),
        _labelled("Setting", _setting(scene, locations)),
        _labelled("Style", movie.style),
        STILL_DIRECTIVE,
    ]
    negatives = _unique(term for profile in cast for term in profile.negative_prompt.split(","))
    if negatives:
        sections.append(f"negative: {negatives}")
    return SEPARATOR.join(section for section in sections if section)


def subtitle_for(cues: Sequence[NarrationCue], start: float, end: float) -> str:
    """The narration spoken while a shot occupies ``[start, end)``."""
    return " ".join(cue.text for cue in cues if cue.overlaps(start, end) and cue.text).strip()


def build_storyboard(
    movie: DirectedMovie,
    *,
    cues: Sequence[NarrationCue] = (),
    profiles: Mapping[str, CharacterProfile] | None = None,
    audio_source: str = "",
    audio_duration: float = 0.0,
) -> Storyboard:
    """Lay ``movie``'s shots on a timeline and map the narration onto them.

    Raises:
        StoryboardError: If no scene carries any shot — there is nothing to
            storyboard until the director has run.
    """
    profiles = profiles or {}
    locations = {location.id.strip().lower(): location for location in movie.locations}

    shots: list[StoryboardShot] = []
    elapsed = 0.0
    for scene in movie.scenes:
        for order, shot in enumerate(scene.shots, start=1):
            start = round(elapsed, 3)
            end = round(elapsed + shot.duration, 3)
            shots.append(
                StoryboardShot(
                    id=len(shots) + 1,
                    scene_id=scene.id,
                    order=order,
                    duration=shot.duration,
                    camera=shot.camera,
                    camera_motion=shot.camera_motion,
                    lens=shot.lens,
                    framing=shot.framing,
                    transition=shot.transition,
                    character=shot.subject or _join(scene.characters),
                    action=shot.action,
                    expression=shot.expression,
                    environment=shot.environment_motion,
                    lighting=shot.lighting,
                    speech_start=start,
                    speech_end=end,
                    subtitle=subtitle_for(cues, start, end),
                    image_prompt=build_image_prompt(movie, scene, shot, profiles, locations),
                    video_prompt=shot.video_prompt,
                    audio_segment=_audio_segment(audio_source, start, end, audio_duration),
                )
            )
            elapsed = end

    if not shots:
        raise StoryboardError(
            "no scene carries any shot; run `director` before building the storyboard"
        )

    return Storyboard(
        title=movie.title,
        style=movie.style,
        total_duration=round(elapsed, 3),
        narration_duration=audio_duration or narration_span(list(cues)),
        shots=tuple(shots),
    )


def _audio_segment(source: str, start: float, end: float, audio_duration: float) -> AudioSegment:
    """The narration slice under a shot, clipped to the track's real length."""
    if not source:
        return AudioSegment()
    limit = audio_duration or end
    return AudioSegment(
        source=source,
        start=round(min(start, limit), 3),
        end=round(min(end, limit), 3),
    )
