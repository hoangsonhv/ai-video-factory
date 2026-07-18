"""Provider contract: protocol, models, errors and retry policy."""

from ai_video_factory.infrastructure.providers.base.errors import (
    AIProviderError,
    AuthenticationError,
    InvalidResponseError,
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
)
from ai_video_factory.infrastructure.providers.base.models import (
    LLMRequest,
    LLMResponse,
    ProviderHealth,
    RawCompletion,
    TokenUsage,
)
from ai_video_factory.infrastructure.providers.base.provider import LLMProvider
from ai_video_factory.infrastructure.providers.base.retry import RetryPolicy

__all__ = [
    "AIProviderError",
    "AuthenticationError",
    "InvalidResponseError",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "ProviderHealth",
    "ProviderUnavailableError",
    "RateLimitError",
    "RawCompletion",
    "RetryPolicy",
    "TimeoutError",
    "TokenUsage",
]
