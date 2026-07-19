"""Story-chapter generator (infrastructure service).

Turns a :class:`StoryOutline` into the full narration prose (a
:class:`StoryChapter`) using the prompt engine and the configured AI provider.
It never calls a vendor SDK directly.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ai_video_factory.domain.value_objects.chapter import StoryChapter
from ai_video_factory.domain.value_objects.outline import StoryOutline
from ai_video_factory.infrastructure.config.settings import Settings
from ai_video_factory.infrastructure.prompts.service import PromptService
from ai_video_factory.infrastructure.providers.base.models import LLMRequest
from ai_video_factory.infrastructure.providers.base.provider import LLMProvider
from ai_video_factory.infrastructure.providers.factory.provider_factory import ProviderFactory
from ai_video_factory.infrastructure.story.chapter_parser import (
    DEFAULT_WORDS_PER_MINUTE,
    parse_chapter,
)
from ai_video_factory.infrastructure.story.errors import ChapterParseError

_PROMPT_NAME = "story/chapter"
# Generous budget so thinking-model reasoning does not truncate the JSON output.
_MAX_TOKENS = 8192
_TEMPERATURE = 0.85
_DEBUG_FILENAME = "chapter_raw_response.txt"
_logger = logging.getLogger(__name__)


class ChapterGenerator:
    """Generates a :class:`StoryChapter` from a :class:`StoryOutline`."""

    def __init__(
        self,
        provider: LLMProvider,
        prompts: PromptService,
        *,
        words_per_minute: int = DEFAULT_WORDS_PER_MINUTE,
        debug_dir: Path | None = None,
    ) -> None:
        self._provider = provider
        self._prompts = prompts
        self._words_per_minute = words_per_minute
        self._debug_dir = debug_dir

    @classmethod
    def from_settings(cls, settings: Settings) -> ChapterGenerator:
        """Build the generator from configuration (provider + prompt root)."""
        provider = ProviderFactory.create(settings)
        prompts = PromptService.create(settings.prompts.root)
        return cls(provider, prompts, debug_dir=settings.app.output_dir / "debug")

    async def generate(self, outline: StoryOutline, *, language: str) -> StoryChapter:
        """Generate the chapter prose, retrying once if parsing fails.

        Raises:
            ChapterParseError: If both attempts return unusable output.
        """
        request = self._build_request(outline, language)
        last_error = ChapterParseError("chapter generation returned unparseable output")
        for _attempt in range(2):
            response = await self._provider.generate(request)
            self._record(request.user_prompt, response.content)
            try:
                return parse_chapter(response.content, words_per_minute=self._words_per_minute)
            except ChapterParseError as exc:
                last_error = exc
        raise last_error

    def _record(self, prompt: str, raw: str) -> None:
        """Log the prompt and raw response, and save the raw response for debugging.

        (The provider abstraction exposes only the response text, not the SDK's
        ``response.parsed``, since no response schema is used.)
        """
        _logger.debug("Chapter prompt:\n%s", prompt)
        _logger.debug("Chapter raw response:\n%s", raw)
        if self._debug_dir is not None:
            self._debug_dir.mkdir(parents=True, exist_ok=True)
            (self._debug_dir / _DEBUG_FILENAME).write_text(raw, encoding="utf-8")

    def _build_request(self, outline: StoryOutline, language: str) -> LLMRequest:
        chapters = "\n".join(
            f"{c.chapter_number}. {c.title} — {c.summary} (cliffhanger: {c.cliffhanger})"
            for c in outline.chapter_outlines
        )
        prompt = self._prompts.render(
            _PROMPT_NAME,
            {
                "title": outline.title,
                "genre": outline.genre,
                "world_setting": outline.world_setting,
                "cultivation_system": outline.cultivation_system,
                "main_character": outline.main_character,
                "supporting_characters": ", ".join(outline.supporting_characters),
                "antagonist": outline.antagonist,
                "story_arc": outline.story_arc,
                "ending": outline.ending,
                "chapter_outlines": chapters,
                "language": language,
            },
        )
        return LLMRequest(
            user_prompt=prompt,
            json_mode=True,
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
            metadata={"stage": "chapter"},
        )
