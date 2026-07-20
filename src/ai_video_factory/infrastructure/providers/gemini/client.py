"""Low-level Gemini client that wraps the official ``google-genai`` SDK.

This is the only module that touches the vendor SDK. It exposes a small typed
:class:`GeminiClient` protocol (so the provider and its tests depend on a seam,
not on the SDK) and translates SDK errors into the provider error hierarchy.
The SDK is imported lazily so importing this module never requires it.
"""

from __future__ import annotations

import re
from typing import Protocol

from ai_video_factory.infrastructure.providers.base.errors import (
    AIProviderError,
    AuthenticationError,
    InvalidResponseError,
    ProviderUnavailableError,
    RateLimitError,
)
from ai_video_factory.infrastructure.providers.base.errors import (
    TimeoutError as ProviderTimeoutError,
)
from ai_video_factory.infrastructure.providers.base.models import LLMRequest, RawCompletion

# The server communicates a back-off hint either as ``'retryDelay': '21s'`` or
# as ``Please retry in 21.00s`` inside the vendor payload.
_RETRY_AFTER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"retryDelay['\"]?\s*:\s*['\"]?\s*([0-9]+(?:\.[0-9]+)?)\s*s", re.IGNORECASE),
    re.compile(r"retry\s+in\s+([0-9]+(?:\.[0-9]+)?)\s*s", re.IGNORECASE),
)


class GeminiClient(Protocol):
    """The subset of Gemini operations the provider needs."""

    async def complete(self, request: LLMRequest, *, model: str) -> RawCompletion: ...

    async def count_tokens(self, text: str, *, model: str) -> int: ...

    async def list_models(self) -> list[str]: ...


def _parse_retry_after(message: str) -> float | None:
    """Extract the server-requested back-off (seconds) from a 429 payload."""
    for pattern in _RETRY_AFTER_PATTERNS:
        match = pattern.search(message)
        if match is not None:
            try:
                return float(match.group(1))
            except ValueError:  # pragma: no cover - defensive
                return None
    return None


def map_status_to_error(status: int, message: str) -> AIProviderError:
    """Translate an HTTP-ish status code into a provider error.

    The raw vendor ``message`` is kept in ``context`` for logs rather than the
    user-facing message, so a 429 quota payload does not leak outward as a wall
    of JSON.
    """
    if status in (401, 403):
        return AuthenticationError(message, context={"status": status})
    if status == 429:
        retry_after = _parse_retry_after(message)
        detail = "rate limit or quota exceeded (HTTP 429)"
        if retry_after is not None:
            detail += f"; retry in {retry_after:.0f}s"
        return RateLimitError(
            detail, retry_after=retry_after, context={"status": status, "detail": message}
        )
    if status in (500, 502, 503, 504):
        return ProviderUnavailableError(message, context={"status": status})
    return InvalidResponseError(message, context={"status": status})


def map_transport_error(exc: Exception) -> AIProviderError:
    """Translate a transport-level failure into a retryable provider error.

    The SDK raises ``APIError`` only once it has an HTTP response. A connection
    timeout, read timeout or dropped socket surfaces as an ``httpx`` (or
    builtin) exception instead, which would otherwise escape untranslated and
    unretried — the transient failure that most often kills a long run.
    """
    name = type(exc).__name__
    if isinstance(exc, TimeoutError) or "Timeout" in name:
        return ProviderTimeoutError(f"Gemini transport timeout ({name}): {exc}")
    return ProviderUnavailableError(f"Gemini transport failure ({name}): {exc}")


def transport_error_types() -> tuple[type[Exception], ...]:
    """The transport exceptions worth translating, httpx included when present."""
    types: list[type[Exception]] = [TimeoutError, ConnectionError]
    try:
        import httpx
    except ImportError:  # pragma: no cover - httpx is a hard dependency
        return tuple(types)
    types.extend((httpx.TimeoutException, httpx.TransportError))
    return tuple(types)


class RealGeminiClient:
    """Concrete :class:`GeminiClient` backed by the ``google-genai`` SDK."""

    def __init__(self, api_key: str) -> None:
        from google import genai  # lazy: only needed when a live client is built
        from google.genai import errors as genai_errors
        from google.genai import types as genai_types

        self._client = genai.Client(api_key=api_key)
        self._types = genai_types
        self._api_error: type[Exception] = genai_errors.APIError
        self._transport_errors = transport_error_types()

    async def complete(self, request: LLMRequest, *, model: str) -> RawCompletion:
        config = self._types.GenerateContentConfig(
            system_instruction=request.system_prompt,
            temperature=request.temperature,
            top_p=request.top_p,
            max_output_tokens=request.max_tokens,
            response_mime_type="application/json" if request.json_mode else None,
        )
        try:
            response = await self._client.aio.models.generate_content(
                model=model, contents=request.user_prompt, config=config
            )
        except self._api_error as exc:
            raise map_status_to_error(int(getattr(exc, "code", 0) or 0), str(exc)) from exc
        except self._transport_errors as exc:
            raise map_transport_error(exc) from exc

        usage = getattr(response, "usage_metadata", None)
        return RawCompletion(
            content=str(getattr(response, "text", "") or ""),
            finish_reason=self._finish_reason(response),
            prompt_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
            completion_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
            total_tokens=int(getattr(usage, "total_token_count", 0) or 0),
            raw={"model": model},
        )

    async def count_tokens(self, text: str, *, model: str) -> int:
        try:
            result = await self._client.aio.models.count_tokens(model=model, contents=text)
        except self._api_error as exc:
            raise map_status_to_error(int(getattr(exc, "code", 0) or 0), str(exc)) from exc
        except self._transport_errors as exc:
            raise map_transport_error(exc) from exc
        return int(getattr(result, "total_tokens", 0) or 0)

    async def list_models(self) -> list[str]:
        try:
            pager = await self._client.aio.models.list()
            names: list[str] = []
            async for model in pager:
                name = getattr(model, "name", None)
                if name:
                    names.append(str(name))
        except self._api_error as exc:
            raise map_status_to_error(int(getattr(exc, "code", 0) or 0), str(exc)) from exc
        except self._transport_errors as exc:
            raise map_transport_error(exc) from exc
        return names

    @staticmethod
    def _finish_reason(response: object) -> str:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return "UNKNOWN"
        reason = getattr(candidates[0], "finish_reason", None)
        return str(getattr(reason, "name", reason) or "UNKNOWN")
