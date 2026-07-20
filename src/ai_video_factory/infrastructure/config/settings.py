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
    model: str = "gemini-3.5-flash"
    timeout: float = Field(default=30.0, gt=0.0)
    retry_count: int = Field(default=3, ge=0)
    director_model: str = "gemini-3.5-flash"

    @field_validator("api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> object | None:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


class ImageProviderSettings(BaseModel):
    """Image (AI) provider settings. The active provider is chosen by
    ``provider``; if ``api_key`` is unset the LLM provider's key is used.

    Defaults to the free, key-less ``pollinations`` provider for the MVP;
    set ``provider=gemini_imagen`` (with a key) to use Google Imagen instead."""

    provider: str = "pollinations"
    api_key: SecretStr | None = None
    model: str = "flux"
    timeout: float = Field(default=60.0, gt=0.0)
    retry_count: int = Field(default=3, ge=0)

    @field_validator("api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> object | None:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


class SpeechProviderSettings(BaseModel):
    """Speech (TTS) provider settings. The active provider is chosen by
    ``provider``; if ``api_key`` is unset the LLM provider's key is used."""

    provider: str = "gemini_tts"
    api_key: SecretStr | None = None
    model: str = "gemini-2.5-flash-preview-tts"
    voice: str = "Kore"
    timeout: float = Field(default=60.0, gt=0.0)
    retry_count: int = Field(default=3, ge=0)

    @field_validator("api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> object | None:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


class TranscriptionProviderSettings(BaseModel):
    """Transcription (speech-to-text) provider settings. The active provider is
    chosen by ``provider``; if ``api_key`` is unset the LLM provider's key is
    used. Used to align subtitles to the narration audio."""

    provider: str = "gemini_transcription"
    api_key: SecretStr | None = None
    model: str = "gemini-flash-latest"
    language: str = "vi"
    timeout: float = Field(default=120.0, gt=0.0)
    retry_count: int = Field(default=3, ge=0)

    @field_validator("api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> object | None:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


class VideoSettings(BaseModel):
    """Final video composition settings (ffmpeg). Portrait TikTok defaults."""

    ffmpeg_path: str = "ffmpeg"
    width: int = Field(default=1080, gt=0)
    height: int = Field(default=1920, gt=0)
    fps: int = Field(default=30, gt=0)
    fade_duration: float = Field(default=0.5, ge=0.0)
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    retry_count: int = Field(default=1, ge=0)


class VideoProviderSettings(BaseModel):
    """AI video-generation provider settings (``VIDEO_PROVIDER`` family).

    The active provider is chosen by ``provider`` (a config ``driver``,
    ADR-005). ``mock`` (local ffmpeg, development) and ``kling`` (Kling AI
    image-to-video) ship today; further drivers register themselves in the
    registry without changing this model.

    ``base_url`` / ``api_key`` / ``model`` are the ``KLING_BASE_URL`` /
    ``KLING_API_KEY`` / ``KLING_MODEL`` settings for the Kling driver.
    Asynchronous providers submit a job and poll: ``poll_interval`` is the gap
    between polls and ``poll_timeout`` the ceiling on one job's total wait,
    independent of ``timeout`` (a single HTTP request).
    """

    provider: str = "mock"
    api_key: SecretStr | None = None
    base_url: str = "https://api.klingai.com"
    model: str = "mock-slideshow"
    timeout: float = Field(default=300.0, gt=0.0)
    retry_count: int = Field(default=1, ge=0)
    poll_interval: float = Field(default=10.0, gt=0.0)
    poll_timeout: float = Field(default=900.0, gt=0.0)
    cost_per_second: float = Field(default=0.0, ge=0.0)

    @field_validator("api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> object | None:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


class OpenRouterSettings(BaseModel):
    """OpenRouter settings, assembled from the ``AIVF_OPENROUTER_*`` variables.

    OpenRouter fronts many models behind one OpenAI-compatible endpoint; the
    ``model`` is a fully-qualified route such as ``deepseek/deepseek-chat-v3``.
    This is the typed object the code consumes; the environment variables that
    populate it are flat (see :class:`Settings`).
    """

    api_key: SecretStr | None = None
    model: str = "deepseek/deepseek-chat-v3"
    base_url: str = "https://openrouter.ai/api/v1"
    timeout: float = Field(default=120.0, gt=0.0)
    retry_count: int = Field(default=3, ge=0)


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
    image_provider: ImageProviderSettings = ImageProviderSettings()
    speech_provider: SpeechProviderSettings = SpeechProviderSettings()
    transcription_provider: TranscriptionProviderSettings = TranscriptionProviderSettings()
    video: VideoSettings = VideoSettings()
    video_provider: VideoProviderSettings = VideoProviderSettings()
    prompts: PromptSettings = PromptSettings()

    # --- Director / OpenRouter -------------------------------------------
    # These are deliberately flat (``AIVF_DIRECTOR_PROVIDER``,
    # ``AIVF_OPENROUTER_API_KEY``, ``AIVF_OPENROUTER_MODEL``) rather than the
    # ``AIVF_SECTION__FIELD`` nesting used elsewhere, because those are the
    # names the operator was given. :attr:`openrouter` re-exposes them to the
    # code as one typed object.
    # Empty means "use the same provider as the rest of the story pipeline"
    # (Gemini by default). The director must not require an OpenRouter key to
    # run; OpenRouter stays available, but only when explicitly asked for with
    # ``AIVF_DIRECTOR_PROVIDER=openrouter``.
    director_provider: str = ""
    openrouter_api_key: SecretStr | None = None
    openrouter_model: str = "deepseek/deepseek-chat-v3"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_timeout: float = Field(default=120.0, gt=0.0)
    openrouter_retry_count: int = Field(default=3, ge=0)

    @field_validator("openrouter_api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> object | None:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @property
    def openrouter(self) -> OpenRouterSettings:
        """The OpenRouter configuration as one typed object."""
        return OpenRouterSettings(
            api_key=self.openrouter_api_key,
            model=self.openrouter_model,
            base_url=self.openrouter_base_url,
            timeout=self.openrouter_timeout,
            retry_count=self.openrouter_retry_count,
        )


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
