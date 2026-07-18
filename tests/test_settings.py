"""Tests for the configuration settings tree."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_video_factory.errors import ConfigurationError
from ai_video_factory.infrastructure.config.settings import Settings, load_settings


def test_defaults_are_applied() -> None:
    settings = Settings(_env_file=None)
    assert settings.app.name == "AI Video Factory"
    assert settings.app.environment == "dev"
    assert settings.logging.level == "INFO"
    assert settings.database.url.startswith("sqlite:///")


def test_environment_variables_override_and_nest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIVF_APP__ENVIRONMENT", "prod")
    monkeypatch.setenv("AIVF_LOGGING__LEVEL", "debug")
    settings = Settings(_env_file=None)
    assert settings.app.environment == "prod"
    assert settings.logging.level == "DEBUG"  # normalised to upper case


def test_env_file_is_loaded(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("AIVF_APP__ENVIRONMENT=test\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)
    assert settings.app.environment == "test"


def test_invalid_log_level_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIVF_LOGGING__LEVEL", "verbose")
    with pytest.raises(ConfigurationError):
        load_settings()


def test_invalid_environment_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIVF_APP__ENVIRONMENT", "staging")
    with pytest.raises(ConfigurationError):
        load_settings()
