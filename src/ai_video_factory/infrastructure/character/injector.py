"""Apply a :class:`CharacterLibrary` to a movie's scene prompts.

Every scene prompt is rewritten as ``<master prompts> | <original prompt> |
negative: <negative terms>`` so the image and video backends always receive the
one canonical description of each character, while the scene's own direction is
preserved verbatim. Deterministic and offline — no AI provider is involved.
"""

from __future__ import annotations

from collections.abc import Iterable

from ai_video_factory.domain.value_objects.character_library import (
    CharacterLibrary,
    CharacterProfile,
)
from ai_video_factory.domain.value_objects.movie import Movie, Scene
from ai_video_factory.infrastructure.character.errors import CharacterLibraryError

NEGATIVE_MARKER = "negative:"
SEPARATOR = " | "


def _join_unique(terms: Iterable[str]) -> str:
    unique: list[str] = []
    seen: set[str] = set()
    for term in terms:
        cleaned = term.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            unique.append(cleaned)
    return ", ".join(unique)


def _compose(master: str, original: str, negative: str) -> str:
    """Prepend ``master``, keep ``original``, append ``negative``."""
    parts = [part for part in (master, original.strip()) if part]
    if negative:
        parts.append(f"{NEGATIVE_MARKER} {negative}")
    return SEPARATOR.join(parts)


class CharacterPromptInjector:
    """Rewrite scene prompts so each references the library, not fresh prose."""

    def __init__(self, library: CharacterLibrary) -> None:
        self._profiles: dict[str, CharacterProfile] = {
            profile.id.strip().lower(): profile for profile in library.characters
        }

    def inject(self, movie: Movie) -> Movie:
        """Return ``movie`` with every scene prompt bound to the library.

        Raises:
            CharacterLibraryError: If a scene references a character id that is
                absent from the library (the two files are out of sync).
        """
        return movie.model_copy(
            update={"scenes": tuple(self._inject_scene(scene) for scene in movie.scenes)}
        )

    def _inject_scene(self, scene: Scene) -> Scene:
        profiles = [self._profile(scene, character_id) for character_id in scene.characters]
        if not profiles:
            return scene
        master = _join_unique(profile.master_prompt for profile in profiles)
        negative = _join_unique(
            term for profile in profiles for term in profile.negative_prompt.split(",")
        )
        return scene.model_copy(
            update={
                "image_prompt": _compose(master, self._strip(scene.image_prompt, master), negative),
                "video_prompt": _compose(master, self._strip(scene.video_prompt, master), negative),
            }
        )

    def _profile(self, scene: Scene, character_id: str) -> CharacterProfile:
        profile = self._profiles.get(character_id.strip().lower())
        if profile is None:
            raise CharacterLibraryError(
                f"scene {scene.id} references unknown character {character_id!r}",
                context={"scene": scene.id, "character": character_id},
            )
        return profile

    @staticmethod
    def _strip(prompt: str, master: str) -> str:
        """Recover the original prompt so injecting twice is a no-op."""
        if not prompt.startswith(master + SEPARATOR):
            return prompt
        remainder = prompt[len(master) + len(SEPARATOR) :]
        head, marker, _ = remainder.rpartition(SEPARATOR + NEGATIVE_MARKER)
        return head if marker else remainder
