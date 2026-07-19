"""UTF-8-safe terminal output helper (interface layer).

Renders a Rich renderable to text in-memory, then writes UTF-8 bytes directly
to stdout so international content (e.g. Vietnamese, Chinese) does not crash
Rich's legacy (cp1252) Windows console encoder.
"""

from __future__ import annotations

import io
import sys

from rich.console import Console, RenderableType


def emit_renderable(renderable: RenderableType) -> None:
    """Print ``renderable`` as UTF-8 bytes (crash-safe on legacy terminals)."""
    sink = io.StringIO()
    Console(file=sink, width=120).print(renderable)
    text = sink.getvalue()
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        Console().print(text, markup=False, highlight=False)
        return
    buffer.write(text.encode("utf-8", errors="backslashreplace"))
    buffer.flush()
