"""Tests for RealPollinationsClient using an httpx MockTransport (no network)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from ai_video_factory.infrastructure.providers.base.errors import (
    InvalidResponseError,
    ProviderUnavailableError,
    RateLimitError,
)
from ai_video_factory.infrastructure.providers.image.base.models import ImageGenerationRequest
from ai_video_factory.infrastructure.providers.image.pollinations.client import (
    RealPollinationsClient,
    aspect_ratio_to_size,
)


def _client(handler: object) -> RealPollinationsClient:
    return RealPollinationsClient(
        base_url="https://img.test",
        timeout=5.0,
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


def test_generate_builds_url_and_returns_bytes() -> None:
    captured: dict[str, httpx.URL] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = request.url
        return httpx.Response(200, content=b"IMG", headers={"content-type": "image/jpeg"})

    client = _client(handler)
    request = ImageGenerationRequest(prompt="a cat", aspect_ratio="9:16", seed=7)

    data = asyncio.run(client.generate(request, model="flux"))

    assert data == b"IMG"
    url = captured["url"]
    assert url.path == "/prompt/a cat"  # decoded form
    assert "/prompt/a%20cat" in str(url)  # the prompt is URL-encoded on the wire
    params = dict(url.params)
    assert params["model"] == "flux"
    assert params["width"] == "576"
    assert params["height"] == "1024"
    assert params["seed"] == "7"
    assert params["nologo"] == "true"


def test_generate_empty_body_raises_invalid_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    client = _client(handler)
    request = ImageGenerationRequest(prompt="x")
    with pytest.raises(InvalidResponseError):
        asyncio.run(client.generate(request, model="flux"))


def test_generate_429_maps_to_rate_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    client = _client(handler)
    request = ImageGenerationRequest(prompt="x")
    with pytest.raises(RateLimitError):
        asyncio.run(client.generate(request, model="flux"))


def test_generate_503_maps_to_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    client = _client(handler)
    request = ImageGenerationRequest(prompt="x")
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(client.generate(request, model="flux"))


def test_network_error_maps_to_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = _client(handler)
    request = ImageGenerationRequest(prompt="x")
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(client.generate(request, model="flux"))


def test_list_models_parses_json_array() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/models"
        return httpx.Response(200, json=["flux", "turbo", "kontext"])

    client = _client(handler)
    assert asyncio.run(client.list_models()) == ["flux", "turbo", "kontext"]


@pytest.mark.parametrize(
    ("ratio", "expected"),
    [
        ("9:16", (576, 1024)),
        ("16:9", (1024, 576)),
        ("1:1", (1024, 1024)),
        ("bogus", (1024, 1024)),
    ],
)
def test_aspect_ratio_to_size(ratio: str, expected: tuple[int, int]) -> None:
    assert aspect_ratio_to_size(ratio) == expected


def test_explicit_width_height_win() -> None:
    captured: dict[str, httpx.URL] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = request.url
        return httpx.Response(200, content=b"IMG")

    client = _client(handler)
    request = ImageGenerationRequest(prompt="x", width=800, height=600)
    asyncio.run(client.generate(request, model="flux"))

    params = dict(captured["url"].params)
    assert params["width"] == "800"
    assert params["height"] == "600"
