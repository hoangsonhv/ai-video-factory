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
        config = self._types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio=request.aspect_ratio or None,
            negative_prompt=request.negative_prompt or None,
            seed=request.seed,
        )
        try:
            response = await self._client.aio.models.generate_images(
                model=model, prompt=request.prompt, config=config
            )
        except self._api_error as exc:
            raise map_status_to_error(int(getattr(exc, "code", 0) or 0), str(exc)) from exc

        images = getattr(response, "generated_images", None) or []
        if not images:
            raise InvalidResponseError("image provider returned no images")
        data = getattr(getattr(images[0], "image", None), "image_bytes", None)
        if not isinstance(data, bytes) or not data:
            raise InvalidResponseError("image provider returned empty image data")
        return data

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
