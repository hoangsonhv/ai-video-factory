"""Low-level Pollinations image client (the only module that does HTTP).

Pollinations (https://pollinations.ai) serves free image generation over a
plain GET request — no API key. This module exposes a small typed
:class:`PollinationsClient` protocol (a test seam) and a concrete
:class:`RealPollinationsClient` backed by ``httpx``, translating transport and
HTTP errors into the shared provider error hierarchy so raw ``httpx``
exceptions never propagate inward.
"""

from __future__ import annotations

import logging
from typing import Protocol
from urllib.parse import quote

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
from ai_video_factory.infrastructure.providers.image.base.models import ImageGenerationRequest

_logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://image.pollinations.ai"
_DEFAULT_MAX_DIMENSION = 1024


def _map_status(status: int, message: str) -> AIProviderError:
    """Translate an HTTP status into a provider error."""
    if status in (401, 403):
        return AuthenticationError(message, context={"status": status})
    if status == 429:
        return RateLimitError(message, context={"status": status})
    if status in (500, 502, 503, 504):
        return ProviderUnavailableError(message, context={"status": status})
    return InvalidResponseError(message, context={"status": status})


def aspect_ratio_to_size(
    aspect_ratio: str, *, max_dimension: int = _DEFAULT_MAX_DIMENSION
) -> tuple[int, int]:
    """Convert a ``W:H`` aspect ratio into pixel ``(width, height)``.

    The longer side is scaled to ``max_dimension``. An unparseable ratio falls
    back to a square of ``max_dimension``.
    """
    try:
        width_part, height_part = aspect_ratio.split(":")
        width, height = int(width_part), int(height_part)
        if width <= 0 or height <= 0:
            raise ValueError(aspect_ratio)
    except (ValueError, AttributeError):
        return max_dimension, max_dimension
    if width >= height:
        return max_dimension, max(1, round(max_dimension * height / width))
    return max(1, round(max_dimension * width / height)), max_dimension


def _dimensions(request: ImageGenerationRequest) -> tuple[int, int]:
    if request.width is not None and request.height is not None:
        return request.width, request.height
    return aspect_ratio_to_size(request.aspect_ratio)


class PollinationsClient(Protocol):
    """The subset of Pollinations operations the provider needs."""

    async def generate(self, request: ImageGenerationRequest, *, model: str) -> bytes: ...

    async def list_models(self) -> list[str]: ...


class RealPollinationsClient:
    """Concrete :class:`PollinationsClient` backed by ``httpx`` (no API key)."""

    def __init__(
        self,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    async def generate(self, request: ImageGenerationRequest, *, model: str) -> bytes:
        width, height = _dimensions(request)
        params: dict[str, str | int] = {
            "model": model,
            "width": width,
            "height": height,
            "nologo": "true",
        }
        if request.seed is not None:
            params["seed"] = request.seed
        url = f"{self._base_url}/prompt/{quote(request.prompt, safe='')}"
        _logger.info(
            "pollinations request | provider=pollinations | model=%s | endpoint=%s | "
            "size=%dx%d | seed=%s",
            model,
            url,
            width,
            height,
            request.seed,
        )
        response = await self._get(url, params=params)
        data = response.content
        if not data:
            raise InvalidResponseError("Pollinations returned empty image data")
        return data

    async def list_models(self) -> list[str]:
        response = await self._get(f"{self._base_url}/models", params=None)
        try:
            payload = response.json()
        except ValueError as exc:
            raise InvalidResponseError("Pollinations returned invalid models JSON") from exc
        if not isinstance(payload, list):
            return []
        return [str(model) for model in payload]

    async def _get(self, url: str, *, params: dict[str, str | int] | None) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Pollinations request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Pollinations request failed: {exc}") from exc
        if response.status_code != httpx.codes.OK:
            self._log_error(url, response)
            raise _map_status(response.status_code, response.text)
        return response

    @staticmethod
    def _log_error(url: str, response: httpx.Response) -> None:
        _logger.error(
            "pollinations request FAILED | endpoint=%s | status=%s | retry_after=%s | body=%s",
            url,
            response.status_code,
            response.headers.get("retry-after"),
            response.text[:500],
        )
