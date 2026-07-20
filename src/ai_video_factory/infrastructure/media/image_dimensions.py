"""Read pixel dimensions from PNG or JPEG image bytes (no third-party deps).

Used to record accurate ``width``/``height`` in the image manifest without
pulling in an imaging library. Returns ``None`` for anything it cannot parse.
"""

from __future__ import annotations

import struct

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# JPEG Start-Of-Frame markers carry the dimensions; these three do not.
_JPEG_NON_SOF = frozenset({0xC4, 0xC8, 0xCC})


def read_image_dimensions(data: bytes) -> tuple[int, int] | None:
    """Return ``(width, height)`` for PNG/JPEG bytes, or ``None`` if unknown."""
    if data[:8] == _PNG_SIGNATURE:
        return _png_size(data)
    if data[:2] == b"\xff\xd8":
        return _jpeg_size(data)
    return None


def _png_size(data: bytes) -> tuple[int, int] | None:
    # IHDR width/height are big-endian uint32 at byte offsets 16 and 20.
    if len(data) < 24:
        return None
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    index = 2
    length = len(data)
    while index + 3 < length:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        # Standalone markers (SOI/EOI/RSTn/TEM) have no length field.
        if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        segment_length = struct.unpack(">H", data[index + 2 : index + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in _JPEG_NON_SOF:
            if index + 9 > length:
                return None
            height, width = struct.unpack(">HH", data[index + 5 : index + 9])
            return width, height
        index += 2 + segment_length
    return None
