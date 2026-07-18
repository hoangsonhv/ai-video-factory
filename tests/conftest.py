"""Shared pytest fixtures.

Ensures the environment is isolated from the developer's own ``AIVF_``
variables so settings tests are deterministic.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _clean_aivf_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove any ``AIVF_`` environment variables before each test."""
    for key in list(os.environ):
        if key.startswith("AIVF_"):
            monkeypatch.delenv(key, raising=False)
