"""Console setup shared by every CLI command.

Windows consoles still default to cp1252, which raises the moment a Vietnamese
character or a Rich spinner glyph reaches stdout. Every command needs the same
guard, so it lives here once rather than being copied into each of them.
"""

from __future__ import annotations

import contextlib
import sys


def ensure_utf8_stdout() -> None:
    """Switch stdout to UTF-8 so non-ASCII text renders instead of crashing.

    A stream that cannot be reconfigured (a pipe, a captured buffer, a test
    runner's stand-in) is left exactly as it is.
    """
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    with contextlib.suppress(ValueError, OSError):  # stream may not be reconfigurable
        reconfigure(encoding="utf-8", errors="backslashreplace")
