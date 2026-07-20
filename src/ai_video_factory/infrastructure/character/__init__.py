"""Character consistency services (infrastructure).

Deterministic, offline stage between the Movie Builder and the media stages:
:class:`CharacterConsistencyService` distils the movie's cast into one profile
per character (``character_library.json``), and
:class:`CharacterPromptInjector` binds every scene prompt to those profiles
(``movie_consistent.json``). No AI provider is involved.
"""

from ai_video_factory.infrastructure.character.errors import CharacterLibraryError
from ai_video_factory.infrastructure.character.injector import CharacterPromptInjector
from ai_video_factory.infrastructure.character.reader import read_character_library, read_movie
from ai_video_factory.infrastructure.character.service import (
    CharacterConsistencyService,
    generate_master_prompt,
    generate_negative_prompt,
    generate_seed,
    merge_duplicates,
    normalize_appearance,
    normalize_outfit,
)
from ai_video_factory.infrastructure.character.writer import (
    write_character_library_json,
    write_consistent_movie_json,
)

__all__ = [
    "CharacterConsistencyService",
    "CharacterLibraryError",
    "CharacterPromptInjector",
    "generate_master_prompt",
    "generate_negative_prompt",
    "generate_seed",
    "merge_duplicates",
    "normalize_appearance",
    "normalize_outfit",
    "read_character_library",
    "read_movie",
    "write_character_library_json",
    "write_consistent_movie_json",
]
