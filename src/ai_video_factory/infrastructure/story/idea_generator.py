"""Story-idea generator (infrastructure service).

Orchestrates the prompt engine and the configured AI provider to produce
structured :class:`StoryIdea` value objects. It never calls a vendor SDK
directly — the provider comes from :class:`ProviderFactory` and the prompt from
:class:`PromptService`.
"""

from __future__ import annotations

from ai_video_factory.domain.value_objects.idea import IdeaBrief, StoryIdea
from ai_video_factory.infrastructure.config.settings import Settings
from ai_video_factory.infrastructure.prompts.service import PromptService
from ai_video_factory.infrastructure.providers.base.models import LLMRequest
from ai_video_factory.infrastructure.providers.base.provider import LLMProvider
from ai_video_factory.infrastructure.providers.factory.provider_factory import ProviderFactory
from ai_video_factory.infrastructure.story.errors import IdeaParseError
from ai_video_factory.infrastructure.story.parser import parse_ideas

_PROMPT_NAME = "story/idea"
_DEFAULT_COUNT = 10
# Generous budget: thinking-capable models (e.g. gemini-*-flash) spend output
# tokens on reasoning, so a small cap truncates the JSON and breaks parsing.
_MAX_TOKENS = 8192
_TEMPERATURE = 0.9


class IdeaGenerator:
    """Generates story ideas from an :class:`IdeaBrief`."""

    def __init__(
        self,
        provider: LLMProvider,
        prompts: PromptService,
        *,
        count: int = _DEFAULT_COUNT,
    ) -> None:
        self._provider = provider
        self._prompts = prompts
        self._count = count

    @classmethod
    def from_settings(cls, settings: Settings) -> IdeaGenerator:
        """Build the generator from configuration (provider + prompt root)."""
        provider = ProviderFactory.create(settings)
        prompts = PromptService.create(settings.prompts.root)
        return cls(provider, prompts)

    async def generate(self, brief: IdeaBrief) -> list[StoryIdea]:
        """Generate ideas for ``brief``, retrying once if parsing fails.

        Raises:
            IdeaParseError: If both attempts return unparseable output.
        """
        request = self._build_request(brief)
        last_error = IdeaParseError("idea generation returned unparseable output")
        for _attempt in range(2):
            response = await self._provider.generate(request)
            try:
                return parse_ideas(response.content)
            except IdeaParseError as exc:
                last_error = exc
        raise last_error

    def _build_request(self, brief: IdeaBrief) -> LLMRequest:
        prompt = self._prompts.render(
            _PROMPT_NAME,
            {
                "topic": brief.topic,
                "style": brief.style,
                "target_platform": brief.target_platform,
                "language": brief.language,
                "count": self._count,
            },
        )
        return LLMRequest(
            user_prompt=prompt,
            json_mode=True,
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
            metadata={"stage": "idea"},
        )
