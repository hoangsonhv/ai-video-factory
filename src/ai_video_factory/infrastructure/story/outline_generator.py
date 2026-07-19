"""Story-outline generator (infrastructure service).

Expands a single :class:`StoryIdea` into a structured :class:`StoryOutline`
using the prompt engine and the configured AI provider. It never calls a vendor
SDK directly — the provider comes from :class:`ProviderFactory` and the prompt
from :class:`PromptService`.
"""

from __future__ import annotations

from ai_video_factory.domain.value_objects.idea import StoryIdea
from ai_video_factory.domain.value_objects.outline import StoryOutline
from ai_video_factory.infrastructure.config.settings import Settings
from ai_video_factory.infrastructure.prompts.service import PromptService
from ai_video_factory.infrastructure.providers.base.models import LLMRequest
from ai_video_factory.infrastructure.providers.base.provider import LLMProvider
from ai_video_factory.infrastructure.providers.factory.provider_factory import ProviderFactory
from ai_video_factory.infrastructure.story.errors import OutlineParseError
from ai_video_factory.infrastructure.story.outline_parser import parse_outline

_PROMPT_NAME = "story/outline"
# Generous budget so thinking-model reasoning does not truncate the JSON output.
_MAX_TOKENS = 8192
_TEMPERATURE = 0.8


class OutlineGenerator:
    """Generates a :class:`StoryOutline` from a :class:`StoryIdea`."""

    def __init__(self, provider: LLMProvider, prompts: PromptService) -> None:
        self._provider = provider
        self._prompts = prompts

    @classmethod
    def from_settings(cls, settings: Settings) -> OutlineGenerator:
        """Build the generator from configuration (provider + prompt root)."""
        provider = ProviderFactory.create(settings)
        prompts = PromptService.create(settings.prompts.root)
        return cls(provider, prompts)

    async def generate(
        self,
        idea: StoryIdea,
        *,
        target_duration: str,
        chapter_count: int,
        language: str,
    ) -> StoryOutline:
        """Generate an outline, retrying once if parsing/validation fails.

        Raises:
            OutlineParseError: If both attempts return unusable output.
        """
        request = self._build_request(idea, target_duration, chapter_count, language)
        last_error = OutlineParseError("outline generation returned unparseable output")
        for _attempt in range(2):
            response = await self._provider.generate(request)
            try:
                return parse_outline(response.content, expected_chapters=chapter_count)
            except OutlineParseError as exc:
                last_error = exc
        raise last_error

    def _build_request(
        self, idea: StoryIdea, target_duration: str, chapter_count: int, language: str
    ) -> LLMRequest:
        prompt = self._prompts.render(
            _PROMPT_NAME,
            {
                "idea_title": idea.title,
                "idea_hook": idea.hook,
                "idea_summary": idea.summary,
                "target_duration": target_duration,
                "chapter_count": chapter_count,
                "language": language,
            },
        )
        return LLMRequest(
            user_prompt=prompt,
            json_mode=True,
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
            metadata={"stage": "outline"},
        )
