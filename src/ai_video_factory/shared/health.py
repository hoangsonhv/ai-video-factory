"""Cross-cutting health/status value type (shared layer).

A small tri-state used by both provider health checks and the ``doctor``
diagnostics. Lives in ``shared`` because it is framework-free and needed by
more than one layer, keeping either side from depending on the other.
"""

from __future__ import annotations

from enum import StrEnum


class HealthStatus(StrEnum):
    """Result of a health or readiness check."""

    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"
