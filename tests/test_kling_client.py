"""Tests for the Kling HTTP client, driven entirely by httpx MockTransport.

No network access: every request is served by an in-process transport.
"""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from ai_video_factory.infrastructure.providers.base.errors import (
    AuthenticationError,
    InvalidResponseError,
    ProviderUnavailableError,
    RateLimitError,
)
from ai_video_factory.infrastructure.providers.base.errors import (
    TimeoutError as ProviderTimeoutError,
)
from ai_video_factory.infrastructure.video.providers.base.models import (
    VideoGenerationRequest,
    VideoJobStatus,
)
from ai_video_factory.infrastructure.video.providers.kling.client import (
    RealKlingClient,
    build_submit_payload,
    encode_image,
    parse_job,
)

BASE_URL = "https://api.klingai.test"


def _image(tmp_path: Path) -> Path:
    path = tmp_path / "001.png"
    path.write_bytes(b"\x89PNG-bytes")
    return path


def _request(**overrides: object) -> VideoGenerationRequest:
    defaults: dict[str, object] = {
        "scene_id": 1,
        "prompt": "a cliff at sunrise",
        "duration": 5.0,
        "aspect_ratio": "9:16",
    }
    defaults.update(overrides)
    return VideoGenerationRequest.model_validate(defaults)


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> RealKlingClient:
    return RealKlingClient(
        api_key="test-key",
        base_url=BASE_URL,
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )


def _job_payload(status: str = "succeed", *, url: str | None = "https://cdn/x.mp4") -> dict:
    videos = [{"id": "v1", "url": url, "duration": "5"}] if url else []
    return {
        "code": 0,
        "message": "SUCCEED",
        "data": {
            "task_id": "task-123",
            "task_status": status,
            "task_result": {"videos": videos},
        },
    }


# --- payload building (pure) -----------------------------------------------


def test_encode_image_base64s_the_file(tmp_path: Path) -> None:
    encoded = encode_image(_image(tmp_path))

    assert base64.b64decode(encoded) == b"\x89PNG-bytes"


def test_encode_image_translates_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(InvalidResponseError, match="cannot read reference image"):
        encode_image(tmp_path / "nope.png")


def test_submit_payload_carries_every_generation_field(tmp_path: Path) -> None:
    payload = build_submit_payload(
        _request(negative_prompt="blurry", seed=42, motion_level=0.75),
        model="kling-v1",
        image=_image(tmp_path),
    )

    assert payload["model_name"] == "kling-v1"
    assert payload["prompt"] == "a cliff at sunrise"
    assert payload["duration"] == "5"
    assert payload["aspect_ratio"] == "9:16"
    assert payload["negative_prompt"] == "blurry"
    assert payload["seed"] == 42
    assert payload["cfg_scale"] == 0.75
    assert base64.b64decode(payload["image"]) == b"\x89PNG-bytes"


def test_submit_payload_omits_empty_optional_fields(tmp_path: Path) -> None:
    payload = build_submit_payload(_request(), model="kling-v1", image=_image(tmp_path))

    assert "negative_prompt" not in payload
    assert "seed" not in payload


# --- response parsing ------------------------------------------------------


def test_parse_job_reads_a_succeeded_task() -> None:
    job = parse_job(_job_payload())

    assert job.task_id == "task-123"
    assert job.status is VideoJobStatus.COMPLETED
    assert job.video_url == "https://cdn/x.mp4"
    assert job.duration == 5.0
    assert job.is_terminal


def test_parse_job_maps_the_vendor_status_vocabulary() -> None:
    assert parse_job(_job_payload("submitted")).status is VideoJobStatus.QUEUED
    assert parse_job(_job_payload("processing")).status is VideoJobStatus.RUNNING
    assert parse_job(_job_payload("failed")).status is VideoJobStatus.FAILED


def test_parse_job_treats_an_unknown_status_as_running() -> None:
    """A vendor vocabulary change must stall a poll, never discard a live job."""
    assert parse_job(_job_payload("renderingV2")).status is VideoJobStatus.RUNNING


def test_parse_job_rejects_a_non_zero_api_code() -> None:
    with pytest.raises(InvalidResponseError, match="rejected the request"):
        parse_job({"code": 1101, "message": "insufficient balance", "data": {}})


def test_parse_job_rejects_a_missing_task_id() -> None:
    with pytest.raises(InvalidResponseError, match="no task id"):
        parse_job({"code": 0, "data": {"task_status": "submitted"}})


def test_parse_job_rejects_a_missing_data_object() -> None:
    with pytest.raises(InvalidResponseError, match="no 'data' object"):
        parse_job({"code": 0})


def test_parse_job_rejects_a_non_object_response() -> None:
    with pytest.raises(InvalidResponseError, match="non-object"):
        parse_job(["not", "an", "object"])


def test_parse_job_tolerates_a_missing_video_and_bad_duration() -> None:
    payload = _job_payload(url=None)
    payload["data"]["task_result"] = {"videos": [{"duration": "not-a-number"}]}

    job = parse_job(payload)

    assert job.video_url is None
    assert job.duration == 0.0


# --- HTTP behaviour --------------------------------------------------------


def test_submit_posts_to_the_image_to_video_endpoint(tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["method"] = request.method
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_job_payload("submitted"))

    job = asyncio.run(
        _client(handler).submit_image_to_video(_request(), model="kling-v1", image=_image(tmp_path))
    )

    assert seen["url"] == f"{BASE_URL}/v1/videos/image2video"
    assert seen["method"] == "POST"
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["model_name"] == "kling-v1"  # type: ignore[index]
    assert job.task_id == "task-123"


def test_get_job_polls_the_task_endpoint() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["method"] = request.method
        return httpx.Response(200, json=_job_payload())

    job = asyncio.run(_client(handler).get_job("task-123"))

    assert seen["url"] == f"{BASE_URL}/v1/videos/image2video/task-123"
    assert seen["method"] == "GET"
    assert job.status is VideoJobStatus.COMPLETED


def test_cancel_job_deletes_the_task() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["method"] = request.method
        return httpx.Response(200, json={"code": 0, "data": {"task_id": "task-123"}})

    asyncio.run(_client(handler).cancel_job("task-123"))

    assert seen["url"] == f"{BASE_URL}/v1/videos/image2video/task-123"
    assert seen["method"] == "DELETE"


def test_download_returns_the_video_bytes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"mp4-bytes")

    assert asyncio.run(_client(handler).download("https://cdn/x.mp4")) == b"mp4-bytes"


def test_download_does_not_leak_credentials_to_the_cdn() -> None:
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, content=b"mp4-bytes")

    asyncio.run(_client(handler).download("https://cdn.example/x.mp4"))

    assert seen["auth"] is None


def test_download_rejects_an_empty_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    with pytest.raises(InvalidResponseError, match="empty video download"):
        asyncio.run(_client(handler).download("https://cdn/x.mp4"))


# --- error translation -----------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (429, RateLimitError),
        (500, ProviderUnavailableError),
        (503, ProviderUnavailableError),
        (400, InvalidResponseError),
    ],
)
def test_http_errors_map_to_the_provider_hierarchy(status: int, expected: type) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"message": "nope"})

    with pytest.raises(expected):
        asyncio.run(_client(handler).get_job("task-123"))


def test_the_api_error_message_is_surfaced() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": 1101, "message": "insufficient balance"})

    with pytest.raises(InvalidResponseError, match="insufficient balance"):
        asyncio.run(_client(handler).get_job("task-123"))


def test_a_transport_timeout_becomes_a_provider_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow")

    with pytest.raises(ProviderTimeoutError, match="timed out"):
        asyncio.run(_client(handler).get_job("task-123"))


def test_a_transport_failure_becomes_provider_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    with pytest.raises(ProviderUnavailableError, match="request failed"):
        asyncio.run(_client(handler).get_job("task-123"))


def test_invalid_json_is_translated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>not json</html>")

    with pytest.raises(InvalidResponseError, match="invalid JSON"):
        asyncio.run(_client(handler).get_job("task-123"))
