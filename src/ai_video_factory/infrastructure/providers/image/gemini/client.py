"""Low-level Gemini Imagen client wrapping the official ``google-genai`` SDK.

The only image module that touches the vendor SDK. Exposes a small typed
:class:`ImagenClient` protocol (a test seam) and translates SDK errors into the
shared provider error hierarchy. The SDK is imported lazily.
"""

from __future__ import annotations

from typing import Protocol

from ai_video_factory.infrastructure.providers.base.errors import InvalidResponseError
from ai_video_factory.infrastructure.providers.gemini.client import map_status_to_error
from ai_video_factory.infrastructure.providers.image.base.models import ImageGenerationRequest


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
        try:
            response = await self._client.aio.models.generate_content(
                model=model, contents=request.prompt, config=config
            )
        except self._api_error as exc:
            raise map_status_to_error(int(getattr(exc, "code", 0) or 0), str(exc)) from exc

        data = self._first_image_bytes(response)
        if not isinstance(data, bytes) or not data:
            raise InvalidResponseError("image provider returned no image data")
        return data

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
        try:
            pager = await self._client.aio.models.list()
            names: list[str] = []
            async for model in pager:
                name = getattr(model, "name", None)
                if name:
                    names.append(str(name))
        except self._api_error as exc:
            raise map_status_to_error(int(getattr(exc, "code", 0) or 0), str(exc)) from exc
        return names
