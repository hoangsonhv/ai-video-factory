"""Tests for the image client's header-extraction diagnostic helper."""

from __future__ import annotations

from ai_video_factory.infrastructure.providers.image.gemini.client import _headers_to_dict


class _WithHeaders:
    def __init__(self, headers: object) -> None:
        self.headers = headers


def test_extracts_and_lowercases_headers() -> None:
    source = _WithHeaders({"Retry-After": "21", "Content-Type": "application/json"})
    assert _headers_to_dict(source) == {
        "retry-after": "21",
        "content-type": "application/json",
    }


def test_none_source_returns_empty() -> None:
    assert _headers_to_dict(None) == {}


def test_object_without_headers_returns_empty() -> None:
    assert _headers_to_dict(object()) == {}
