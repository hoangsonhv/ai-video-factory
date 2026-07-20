"""Low-level Gemini Imagen client wrapping the official ``google-genai`` SDK.

The only image module that touches the vendor SDK. Exposes a small typed
:class:`ImagenClient` protocol (a test seam) and translates SDK errors into the
shared provider error hierarchy. The SDK is imported lazily.
"""

from __future__ import annotations

import logging
from typing import Protocol

from ai_video_factory.infrastructure.providers.base.errors import InvalidResponseError
from ai_video_factory.infrastructure.providers.gemini.client import map_status_to_error
from ai_video_factory.infrastructure.providers.image.base.models import ImageGenerationRequest

_logger = logging.getLogger(__name__)

# An api-key client talks to the Gemini Developer API; there is no GCP project
# and the region is always global. The endpoint is derived from the model.
_PROVIDER_LABEL = "gemini_imagen (Gemini Developer API, api-key auth, region=global)"
_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


def _headers_to_dict(source: object) -> dict[str, str]:
    """Best-effort extraction of HTTP headers from a response or error object."""
    headers = getattr(source, "headers", None)
    if headers is None:
        return {}
    try:
        return {str(key).lower(): str(value) for key, value in dict(headers).items()}
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return {}


class ImagenClient(Protocol):
    """The subset of Imagen operations the provider needs."""

    async def generate(self, request: ImageGenerationRequest, *, model: str) -> bytes: ...

    async def list_models(self) -> list[str]: ...


class RealImagenClient:
    """Concrete :class:`ImagenClient` backed by ``google-genai`` (Imagen)."""

    def __init__(self, api_key: str) -> None:
        from google import genai  # lazy: only needed when a live client is built
        from google.genai import errors as genai_errors
        from google.genai import types as genai_types

        self._client = genai.Client(api_key=api_key)
        self._types = genai_types
        self._api_error: type[Exception] = genai_errors.APIError

    async def generate(self, request: ImageGenerationRequest, *, model: str) -> bytes:
        # An api-key client runs in Gemini Developer API mode. There, image
        # generation is served by the ``gemini-*-image`` models via
        # ``generate_content`` — the Imagen ``:predict`` endpoint is not
        # available to Developer API keys. ``negative_prompt`` is unsupported in
        # this mode and is therefore not forwarded; ``aspect_ratio`` is passed
        # through ``image_config`` when provided.
        image_config = (
            self._types.ImageConfig(aspect_ratio=request.aspect_ratio)
            if request.aspect_ratio
            else None
        )
        config = self._types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=image_config,
        )
        _logger.info(
            "image request | provider=%s | model=%s | endpoint=%s | "
            "config={response_modalities=['IMAGE'], aspect_ratio=%r}",
            _PROVIDER_LABEL,
            model,
            _ENDPOINT_TEMPLATE.format(model=model),
            request.aspect_ratio or None,
        )
        try:
            response = await self._client.aio.models.generate_content(
                model=model, contents=request.prompt, config=config
            )
        except self._api_error as exc:
            self._log_api_error(model, exc)
            raise map_status_to_error(int(getattr(exc, "code", 0) or 0), str(exc)) from exc

        self._log_response(model, response)
        data = self._first_image_bytes(response)
        if not isinstance(data, bytes) or not data:
            raise InvalidResponseError("image provider returned no image data")
        return data

    @staticmethod
    def _log_response(model: str, response: object) -> None:
        """Log the response headers of a successful image request."""
        headers = _headers_to_dict(getattr(response, "sdk_http_response", None))
        _logger.info(
            "image response | model=%s | status=OK | retry_after=%s | response_headers=%s",
            model,
            headers.get("retry-after"),
            headers or "<unavailable>",
        )

    @staticmethod
    def _log_api_error(model: str, exc: Exception) -> None:
        """Log the full diagnostic detail of a failed image request."""
        headers = _headers_to_dict(getattr(exc, "response", None))
        _logger.error(
            "image request FAILED | model=%s | status=%s | retry_after=%s | "
            "response_headers=%s | error_body=%s",
            model,
            getattr(exc, "code", None),
            headers.get("retry-after"),
            headers or "<unavailable>",
            getattr(exc, "details", None) or str(exc),
        )

    @staticmethod
    def _first_image_bytes(response: object) -> bytes | None:
        """Return the bytes of the first inline image part, if any."""
        for candidate in getattr(response, "candidates", None) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                data = getattr(getattr(part, "inline_data", None), "data", None)
                if isinstance(data, bytes) and data:
                    return data
        return None

    async def list_models(self) -> list[str]:
        _logger.info(
            "image list_models | provider=%s | endpoint=%s",
            _PROVIDER_LABEL,
            "https://generativelanguage.googleapis.com/v1beta/models",
        )
        try:
            pager = await self._client.aio.models.list()
            names: list[str] = []
            async for model in pager:
                name = getattr(model, "name", None)
                if name:
                    names.append(str(name))
        except self._api_error as exc:
            self._log_api_error("<list_models>", exc)
            raise map_status_to_error(int(getattr(exc, "code", 0) or 0), str(exc)) from exc
        return names
