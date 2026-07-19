"""Shared pytest fixtures.

Isolates tests from the developer's own configuration — both ``AIVF_``
environment variables and any local ``.env`` file (which may hold a real API
key) — so settings are deterministic and no test can accidentally use a live
provider.
"""

from __future__ import annotations

import os

import pytest

from ai_video_factory.infrastructure.config.settings import Settings


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip ``AIVF_`` env vars and stop settings from reading a local ``.env``."""
    for key in list(os.environ):
        if key.startswith("AIVF_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
