"""Application configuration (infrastructure layer).

A single, typed settings tree loaded via ``pydantic-settings`` following the
approved architecture (docs/ai-tool.md §8). Settings are validated once at
load time; invalid configuration raises :class:`ConfigurationError` so the
application fails fast rather than mid-run (ADR-008).

Precedence: explicit init values → environment variables (``AIVF_`` prefix,
``__`` nesting) → ``.env`` file → in-code defaults.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai_video_factory.errors import ConfigurationError

_VALID_LOG_LEVELS: frozenset[str] = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})


class AppSettings(BaseModel):
    """General application settings."""

    name: str = "AI Video Factory"
    environment: Literal["dev", "test", "prod"] = "dev"
    output_dir: Path = Path("output")


class DatabaseSettings(BaseModel):
    """SQLite database settings (ADR-003)."""

    path: Path = Path("data/factory.db")

    @property
    def url(self) -> str:
        """SQLAlchemy-style connection URL for the configured database."""
        return f"sqlite:///{self.path.as_posix()}"


class LoggingSettings(BaseModel):
    """Logging settings for the Rich console and rotating file handlers."""

    level: str = "INFO"
    console: bool = True
    file_enabled: bool = True
    file_path: Path = Path("logs/aivideo.log")
    max_bytes: int = Field(default=10_485_760, ge=1)
    backup_count: int = Field(default=5, ge=0)

    @field_validator("level", mode="before")
    @classmethod
    def _normalise_level(cls, value: object) -> str:
        level = str(value).upper()
        if level not in _VALID_LOG_LEVELS:
            expected = ", ".join(sorted(_VALID_LOG_LEVELS))
            raise ValueError(f"invalid log level {value!r}; expected one of: {expected}")
        return level


class ProviderSettings(BaseModel):
    """AI (LLM) provider settings. The active provider is chosen by ``provider``
    (a config ``driver``); the API key is a secret and never serialized."""

    provider: str = "gemini"
    api_key: SecretStr | None = None
    model: str = "gemini-2.0-flash"
    timeout: float = Field(default=30.0, gt=0.0)
    retry_count: int = Field(default=3, ge=0)

    @field_validator("api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> object | None:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


class PromptSettings(BaseModel):
    """Prompt engine settings. ``root`` is the directory holding templates."""

    root: Path = Path("prompts")


class Settings(BaseSettings):
    """Root settings tree composed of the per-section models."""

    model_config = SettingsConfigDict(
        env_prefix="AIVF_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app: AppSettings = AppSettings()
    database: DatabaseSettings = DatabaseSettings()
    logging: LoggingSettings = LoggingSettings()
    provider: ProviderSettings = ProviderSettings()
    prompts: PromptSettings = PromptSettings()


def load_settings() -> Settings:
    """Load and validate the settings tree.

    Returns:
        The validated :class:`Settings` instance.

    Raises:
        ConfigurationError: If any value fails validation.
    """
    try:
        return Settings()
    except ValidationError as exc:
        raise ConfigurationError(
            "Invalid application configuration", context={"errors": exc.errors()}
        ) from exc
