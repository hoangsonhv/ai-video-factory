"""Tests for the dependency-free PNG/JPEG dimension reader."""

from __future__ import annotations

import struct

from ai_video_factory.infrastructure.media.image_dimensions import read_image_dimensions

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png(width: int, height: int) -> bytes:
    return (
        _PNG_SIGNATURE
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
        + b"\x00"
    )


def _jpeg(width: int, height: int) -> bytes:
    # SOI, then a baseline SOF0 segment carrying height then width.
    sof = b"\xff\xc0" + struct.pack(">H", 17) + b"\x08" + struct.pack(">HH", height, width)
    return b"\xff\xd8" + b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + sof


def test_reads_png_dimensions() -> None:
    assert read_image_dimensions(_png(1024, 576)) == (1024, 576)


def test_reads_jpeg_dimensions() -> None:
    assert read_image_dimensions(_jpeg(576, 1024)) == (576, 1024)


def test_unknown_format_returns_none() -> None:
    assert read_image_dimensions(b"not an image") is None


def test_truncated_png_returns_none() -> None:
    assert read_image_dimensions(_PNG_SIGNATURE + b"\x00\x00") is None
