"""Movie Builder (infrastructure service).

Turns a :class:`StoryChapter` into a structured :class:`Movie` — persistent
characters (fixed appearance), locations, and cinematic scenes with camera
language, action, emotion, and image/video prompts — using the prompt engine
and the configured AI provider. It never calls a vendor SDK directly, and it
does not touch the existing story/image/voice/subtitle/video stages.
"""

from __future__ import annotations

from ai_video_factory.domain.value_objects.chapter import StoryChapter
from ai_video_factory.domain.value_objects.movie import Movie
from ai_video_factory.infrastructure.config.settings import Settings
from ai_video_factory.infrastructure.prompts.service import PromptService
from ai_video_factory.infrastructure.providers.base.models import LLMRequest
from ai_video_factory.infrastructure.providers.base.provider import LLMProvider
from ai_video_factory.infrastructure.providers.factory.provider_factory import ProviderFactory
from ai_video_factory.infrastructure.story.errors import MovieBuildError
from ai_video_factory.infrastructure.story.movie_parser import parse_movie

_PROMPT_NAME = "story/movie"
# Generous budget: the movie bible (characters + many scenes) is a large JSON.
_MAX_TOKENS = 8192
_TEMPERATURE = 0.8

DEFAULT_STYLE = "cinematic"
DEFAULT_GENRE = ""


class MovieBuilder:
    """Builds a structured :class:`Movie` from a :class:`StoryChapter`."""

    def __init__(self, provider: LLMProvider, prompts: PromptService) -> None:
        self._provider = provider
        self._prompts = prompts

    @classmethod
    def from_settings(cls, settings: Settings) -> MovieBuilder:
        """Build the Movie Builder from configuration (provider + prompt root)."""
        provider = ProviderFactory.create(settings)
        prompts = PromptService.create(settings.prompts.root)
        return cls(provider, prompts)

    async def build(
        self,
        chapter: StoryChapter,
        *,
        style: str = DEFAULT_STYLE,
        genre: str = DEFAULT_GENRE,
        language: str = "vi",
    ) -> Movie:
        """Build the movie, retrying once if parsing fails.

        Raises:
            MovieBuildError: If both attempts return unusable output.
        """
        duration = chapter.estimated_duration_seconds
        request = self._build_request(chapter, style, genre, duration, language)
        last_error = MovieBuildError("movie generation returned unparseable output")
        for _attempt in range(2):
            response = await self._provider.generate(request)
            try:
                return parse_movie(response.content, style=style, genre=genre, duration=duration)
            except MovieBuildError as exc:
                last_error = exc
        raise last_error

    def _build_request(
        self,
        chapter: StoryChapter,
        style: str,
        genre: str,
        duration: int,
        language: str,
    ) -> LLMRequest:
        prompt = self._prompts.render(
            _PROMPT_NAME,
            {
                "chapter_title": chapter.title,
                "chapter_content": chapter.content,
                "style": style,
                "genre": genre,
                "duration": duration,
                "language": language,
            },
        )
        return LLMRequest(
            user_prompt=prompt,
            json_mode=True,
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
            metadata={"stage": "movie"},
        )
