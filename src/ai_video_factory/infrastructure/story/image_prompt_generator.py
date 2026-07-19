"""Image-prompt generator (infrastructure service).

Turns a :class:`StoryChapter` into a list of cinematic :class:`ImagePrompt`
specs using the prompt engine and the configured AI provider. It generates the
prompt *text* only — no images are produced. It never calls a vendor SDK
directly.
"""

from __future__ import annotations

from ai_video_factory.domain.value_objects.chapter import StoryChapter
from ai_video_factory.domain.value_objects.image_prompt import ImagePrompt
from ai_video_factory.infrastructure.config.settings import Settings
from ai_video_factory.infrastructure.prompts.service import PromptService
from ai_video_factory.infrastructure.providers.base.models import LLMRequest
from ai_video_factory.infrastructure.providers.base.provider import LLMProvider
from ai_video_factory.infrastructure.providers.factory.provider_factory import ProviderFactory
from ai_video_factory.infrastructure.story.errors import ImagePromptParseError
from ai_video_factory.infrastructure.story.image_prompt_parser import parse_image_prompts

_PROMPT_NAME = "image/image_prompt"
# Generous budget so thinking-model reasoning does not truncate the JSON output.
_MAX_TOKENS = 8192
_TEMPERATURE = 0.9

DEFAULT_STYLE = "cinematic"
DEFAULT_ASPECT_RATIO = "9:16"
DEFAULT_COUNT = 6


class ImagePromptGenerator:
    """Generates cinematic image prompts from a :class:`StoryChapter`."""

    def __init__(self, provider: LLMProvider, prompts: PromptService) -> None:
        self._provider = provider
        self._prompts = prompts

    @classmethod
    def from_settings(cls, settings: Settings) -> ImagePromptGenerator:
        """Build the generator from configuration (provider + prompt root)."""
        provider = ProviderFactory.create(settings)
        prompts = PromptService.create(settings.prompts.root)
        return cls(provider, prompts)

    async def generate(
        self,
        chapter: StoryChapter,
        *,
        style: str = DEFAULT_STYLE,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        count: int = DEFAULT_COUNT,
        language: str = "vi",
    ) -> list[ImagePrompt]:
        """Generate image prompts, retrying once if parsing fails.

        Raises:
            ImagePromptParseError: If both attempts return unusable output.
        """
        request = self._build_request(chapter, style, aspect_ratio, count, language)
        last_error = ImagePromptParseError("image prompt generation returned unparseable output")
        for _attempt in range(2):
            response = await self._provider.generate(request)
            try:
                return parse_image_prompts(response.content, style=style, aspect_ratio=aspect_ratio)
            except ImagePromptParseError as exc:
                last_error = exc
        raise last_error

    def _build_request(
        self,
        chapter: StoryChapter,
        style: str,
        aspect_ratio: str,
        count: int,
        language: str,
    ) -> LLMRequest:
        prompt = self._prompts.render(
            _PROMPT_NAME,
            {
                "chapter_title": chapter.title,
                "chapter_content": chapter.content,
                "style": style,
                "aspect_ratio": aspect_ratio,
                "count": count,
                "language": language,
            },
        )
        return LLMRequest(
            user_prompt=prompt,
            json_mode=True,
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
            metadata={"stage": "image_prompt"},
        )
