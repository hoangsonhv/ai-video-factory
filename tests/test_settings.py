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


def test_prompt_root_default_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    assert Settings(_env_file=None).prompts.root == Path("prompts")
    monkeypatch.setenv("AIVF_PROMPTS__ROOT", "custom/prompts")
    assert load_settings().prompts.root == Path("custom/prompts")


def test_provider_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.provider.provider == "gemini"
    assert settings.provider.api_key is None
    assert settings.provider.model == "gemini-2.0-flash"
    assert settings.provider.timeout == 30.0
    assert settings.provider.retry_count == 3


def test_provider_blank_api_key_becomes_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIVF_PROVIDER__API_KEY", "   ")
    settings = load_settings()
    assert settings.provider.api_key is None


def test_provider_api_key_is_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIVF_PROVIDER__API_KEY", "super-secret")
    settings = load_settings()
    assert settings.provider.api_key is not None
    assert "super-secret" not in str(settings.provider)
    assert settings.provider.api_key.get_secret_value() == "super-secret"


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
