"""Low-level Kling AI client (the only module that does HTTP).

Exposes a small typed :class:`KlingClient` protocol (a test seam) and a
concrete :class:`RealKlingClient` backed by ``httpx``, translating transport
and HTTP errors into the shared provider error hierarchy so raw ``httpx``
exceptions never propagate inward.

Endpoint shapes follow Kling's published image-to-video API:

- ``POST {base}/v1/videos/image2video`` → ``{data: {task_id, task_status}}``
- ``GET  {base}/v1/videos/image2video/{task_id}`` →
  ``{data: {task_id, task_status, task_status_msg, task_result: {videos: [...]}}}``
- ``DELETE {base}/v1/videos/image2video/{task_id}`` (cancellation)

The base URL, model and credentials are all configuration, so a change on the
vendor's side is a settings change rather than a code change. Authentication
sends the configured key as a bearer token — Kling mints that token from an
access-key/secret-key pair, so ``KLING_API_KEY`` holds the resulting JWT.

**Unverified against the live service:** no Kling credentials were available
when this was written, so every test drives it through an ``httpx``
``MockTransport``. Response parsing is deliberately tolerant (several field
spellings accepted) and any mismatch surfaces as ``InvalidResponseError``
rather than a crash.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
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
from ai_video_factory.infrastructure.video.providers.base.models import VideoGenerationRequest
from ai_video_factory.infrastructure.video.providers.kling.models import KlingJob, map_task_status

_logger = logging.getLogger(__name__)

IMAGE_TO_VIDEO_PATH = "/v1/videos/image2video"


def _map_status(status: int, message: str) -> AIProviderError:
    """Translate an HTTP status into a provider error."""
    if status in (401, 403):
        return AuthenticationError(message, context={"status": status})
    if status == 429:
        return RateLimitError(message, context={"status": status})
    if status in (500, 502, 503, 504):
        return ProviderUnavailableError(message, context={"status": status})
    return InvalidResponseError(message, context={"status": status})


def encode_image(path: Path) -> str:
    """Base64-encode the reference image Kling animates.

    Raises:
        InvalidResponseError: If the image cannot be read.
    """
    try:
        return base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError as exc:
        raise InvalidResponseError(f"cannot read reference image {path}: {exc}") from exc


def build_submit_payload(
    request: VideoGenerationRequest, *, model: str, image: Path
) -> dict[str, Any]:
    """Build the image-to-video request body (pure, unit-testable)."""
    payload: dict[str, Any] = {
        "model_name": model,
        "image": encode_image(image),
        "prompt": request.prompt,
        "duration": str(round(request.duration)),
        "aspect_ratio": request.aspect_ratio,
        "cfg_scale": round(request.motion_level, 2),
    }
    if request.negative_prompt:
        payload["negative_prompt"] = request.negative_prompt
    if request.seed is not None:
        payload["seed"] = request.seed
    return payload


def _first_video(task_result: object) -> dict[str, Any]:
    if not isinstance(task_result, dict):
        return {}
    videos = task_result.get("videos")
    if isinstance(videos, list) and videos and isinstance(videos[0], dict):
        return videos[0]
    return {}


def parse_job(payload: object) -> KlingJob:
    """Normalize a Kling task payload into a :class:`KlingJob`.

    Raises:
        InvalidResponseError: If the payload carries no usable task.
    """
    if not isinstance(payload, dict):
        raise InvalidResponseError("Kling returned a non-object response")

    code = payload.get("code")
    if isinstance(code, int) and code != 0:
        raise InvalidResponseError(
            f"Kling rejected the request: {payload.get('message', 'unknown error')}",
            context={"code": code},
        )

    data = payload.get("data")
    if not isinstance(data, dict):
        raise InvalidResponseError("Kling response carried no 'data' object")

    task_id = str(data.get("task_id") or data.get("id") or "").strip()
    if not task_id:
        raise InvalidResponseError("Kling response carried no task id")

    video = _first_video(data.get("task_result"))
    raw_duration = video.get("duration", 0)
    try:
        duration = float(raw_duration)
    except (TypeError, ValueError):
        duration = 0.0

    return KlingJob(
        task_id=task_id,
        status=map_task_status(str(data.get("task_status", ""))),
        video_url=str(video["url"]) if video.get("url") else None,
        duration=duration,
        message=str(data.get("task_status_msg") or payload.get("message") or ""),
    )


class KlingClient(Protocol):
    """The subset of Kling operations the provider needs."""

    async def submit_image_to_video(
        self, request: VideoGenerationRequest, *, model: str, image: Path
    ) -> KlingJob: ...

    async def get_job(self, task_id: str) -> KlingJob: ...

    async def cancel_job(self, task_id: str) -> None: ...

    async def download(self, url: str) -> bytes: ...


class RealKlingClient:
    """Concrete :class:`KlingClient` backed by ``httpx``."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout: float = 60.0,
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
        }

    async def submit_image_to_video(
        self, request: VideoGenerationRequest, *, model: str, image: Path
    ) -> KlingJob:
        url = f"{self._base_url}{IMAGE_TO_VIDEO_PATH}"
        payload = build_submit_payload(request, model=model, image=image)
        _logger.info(
            "kling submit | scene=%d | model=%s | duration=%ss | aspect=%s",
            request.scene_id,
            model,
            payload["duration"],
            request.aspect_ratio,
        )
        response = await self._request("POST", url, json=payload)
        return parse_job(self._json(response))

    async def get_job(self, task_id: str) -> KlingJob:
        url = f"{self._base_url}{IMAGE_TO_VIDEO_PATH}/{task_id}"
        return parse_job(self._json(await self._request("GET", url)))

    async def cancel_job(self, task_id: str) -> None:
        url = f"{self._base_url}{IMAGE_TO_VIDEO_PATH}/{task_id}"
        await self._request("DELETE", url)

    async def download(self, url: str) -> bytes:
        response = await self._request("GET", url, authenticated=False)
        if not response.content:
            raise InvalidResponseError("Kling returned an empty video download")
        return response.content

    @staticmethod
    def _json(response: httpx.Response) -> object:
        try:
            return response.json()
        except ValueError as exc:
            raise InvalidResponseError("Kling returned invalid JSON") from exc

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.request(
                    method,
                    url,
                    json=json,
                    headers=self._headers if authenticated else None,
                    follow_redirects=True,
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Kling request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Kling request failed: {exc}") from exc
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
            return response.text[:500]
        if isinstance(payload, dict) and payload.get("message"):
            return f"Kling error {response.status_code}: {payload['message']}"
        return f"Kling error {response.status_code}: {response.text[:500]}"

    @staticmethod
    def _log_error(method: str, url: str, response: httpx.Response) -> None:
        _logger.error(
            "kling request FAILED | %s %s | status=%s | retry_after=%s | body=%s",
            method,
            url,
            response.status_code,
            response.headers.get("retry-after"),
            response.text[:500],
        )
