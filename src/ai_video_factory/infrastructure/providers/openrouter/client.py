"""Low-level OpenRouter client (the only module that does HTTP).

OpenRouter fronts many vendors behind one OpenAI-compatible endpoint:

- ``POST {base}/chat/completions`` → ``{choices: [{message: {content}, ...}], usage: {...}}``
- ``GET  {base}/models``           → ``{data: [{id, ...}]}``

Exposes a small typed :class:`OpenRouterClient` protocol (a test seam) and a
concrete :class:`RealOpenRouterClient` backed by ``httpx``, translating
transport and HTTP errors into the shared provider error hierarchy so raw
``httpx`` exceptions never propagate inward.

**Unverified against the live service:** no OpenRouter credentials were
available when this was written, so every test drives it through an ``httpx``
``MockTransport``. Response parsing is tolerant and any mismatch surfaces as
``InvalidResponseError`` rather than a crash.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

import httpx

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

_logger = logging.getLogger(__name__)

CHAT_COMPLETIONS_PATH = "/chat/completions"
MODELS_PATH = "/models"

# Sent so OpenRouter can attribute traffic; both are optional on their side.
REFERER = "https://github.com/ai-video-factory"
TITLE = "AI Video Factory"


def _map_status(status: int, message: str) -> AIProviderError:
    """Translate an HTTP status into a provider error."""
    if status in (401, 403):
        return AuthenticationError(message, context={"status": status})
    if status == 429:
        return RateLimitError(message, context={"status": status})
    if status in (500, 502, 503, 504):
        return ProviderUnavailableError(message, context={"status": status})
    return InvalidResponseError(message, context={"status": status})


def build_payload(request: LLMRequest, *, model: str) -> dict[str, Any]:
    """Build the chat-completions body (pure, unit-testable)."""
    messages: list[dict[str, str]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.user_prompt})

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": request.temperature,
        "top_p": request.top_p,
        "max_tokens": request.max_tokens,
    }
    if request.json_mode:
        payload["response_format"] = {"type": "json_object"}
    return payload


def _usage(payload: dict[str, Any]) -> tuple[int, int, int]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return 0, 0, 0

    def _count(key: str) -> int:
        value = usage.get(key)
        return int(value) if isinstance(value, int | float) else 0

    return _count("prompt_tokens"), _count("completion_tokens"), _count("total_tokens")


def parse_completion(payload: object, *, model: str) -> RawCompletion:
    """Normalize a chat-completions response into a :class:`RawCompletion`.

    Raises:
        InvalidResponseError: If the payload carries no usable choice.
    """
    if not isinstance(payload, dict):
        raise InvalidResponseError("OpenRouter returned a non-object response")

    error = payload.get("error")
    if isinstance(error, dict) and error.get("message"):
        raise InvalidResponseError(f"OpenRouter error: {error['message']}")

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise InvalidResponseError("OpenRouter response carried no choices")

    choice = choices[0]
    message = choice.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise InvalidResponseError("OpenRouter returned an empty completion")

    prompt_tokens, completion_tokens, total_tokens = _usage(payload)
    return RawCompletion(
        content=content,
        finish_reason=str(choice.get("finish_reason") or "stop"),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens or prompt_tokens + completion_tokens,
        raw={"model": str(payload.get("model") or model)},
    )


class OpenRouterClient(Protocol):
    """The subset of OpenRouter operations the provider needs."""

    async def complete(self, request: LLMRequest, *, model: str) -> RawCompletion: ...

    async def list_models(self) -> list[str]: ...


class RealOpenRouterClient:
    """Concrete :class:`OpenRouterClient` backed by ``httpx``."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": REFERER,
            "X-Title": TITLE,
        }

    async def complete(self, request: LLMRequest, *, model: str) -> RawCompletion:
        payload = build_payload(request, model=model)
        _logger.info(
            "openrouter request | model=%s | json_mode=%s | max_tokens=%d",
            model,
            request.json_mode,
            request.max_tokens,
        )
        response = await self._request(
            "POST", f"{self._base_url}{CHAT_COMPLETIONS_PATH}", json=payload
        )
        return parse_completion(self._json(response), model=model)

    async def list_models(self) -> list[str]:
        response = await self._request("GET", f"{self._base_url}{MODELS_PATH}")
        payload = self._json(response)
        if not isinstance(payload, dict):
            return []
        data = payload.get("data")
        if not isinstance(data, list):
            return []
        return [str(item["id"]) for item in data if isinstance(item, dict) and item.get("id")]

    @staticmethod
    def _json(response: httpx.Response) -> object:
        try:
            return response.json()
        except ValueError as exc:
            raise InvalidResponseError("OpenRouter returned invalid JSON") from exc

    async def _request(
        self, method: str, url: str, *, json: dict[str, Any] | None = None
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.request(method, url, json=json, headers=self._headers)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"OpenRouter request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"OpenRouter request failed: {exc}") from exc
        if response.status_code >= httpx.codes.BAD_REQUEST:
            self._log_error(method, url, response)
            raise _map_status(response.status_code, self._error_message(response))
        return response

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        """Prefer the API's own message over the raw body."""
        try:
            payload = response.json()
        except ValueError:
            return f"OpenRouter error {response.status_code}: {response.text[:500]}"
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict) and error.get("message"):
            return f"OpenRouter error {response.status_code}: {error['message']}"
        return f"OpenRouter error {response.status_code}: {response.text[:500]}"

    @staticmethod
    def _log_error(method: str, url: str, response: httpx.Response) -> None:
        _logger.error(
            "openrouter request FAILED | %s %s | status=%s | body=%s",
            method,
            url,
            response.status_code,
            response.text[:500],
        )
