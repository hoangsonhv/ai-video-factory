"""Tests for the OpenRouter provider, the factory wiring and the director's use of it."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import SecretStr

from ai_video_factory.errors import ConfigurationError
from ai_video_factory.infrastructure.config.settings import (
    OpenRouterSettings,
    ProviderSettings,
    Settings,
    load_settings,
)
from ai_video_factory.infrastructure.director.service import DirectorService
from ai_video_factory.infrastructure.providers.base.errors import (
    AuthenticationError,
    ProviderUnavailableError,
)
from ai_video_factory.infrastructure.providers.base.models import LLMRequest, RawCompletion
from ai_video_factory.infrastructure.providers.base.provider import LLMProvider
from ai_video_factory.infrastructure.providers.factory.provider_factory import ProviderFactory
from ai_video_factory.infrastructure.providers.gemini.provider import GeminiProvider
from ai_video_factory.infrastructure.providers.openrouter.provider import OpenRouterProvider
from ai_video_factory.shared.health import HealthStatus

MODEL = "deepseek/deepseek-chat-v3"


class _FakeClient:
    """A scripted OpenRouterClient."""

    def __init__(self, *, outcome: object = None, models: list[str] | None = None) -> None:
        self._outcome = outcome
        self._models = models if models is not None else [MODEL]
        self.requests: list[tuple[LLMRequest, str]] = []

    async def complete(self, request: LLMRequest, *, model: str) -> RawCompletion:
        self.requests.append((request, model))
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return RawCompletion(
            content='{"scenes":[]}',
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )

    async def list_models(self) -> list[str]:
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._models


def _settings(**overrides: object) -> OpenRouterSettings:
    defaults: dict[str, object] = {"api_key": "test-key", "model": MODEL, "retry_count": 1}
    defaults.update(overrides)
    return OpenRouterSettings.model_validate(defaults)


def _provider(client: _FakeClient | None = None, **overrides: object) -> OpenRouterProvider:
    return OpenRouterProvider(_settings(**overrides), client=client or _FakeClient())


# --- the provider contract -------------------------------------------------


def test_it_satisfies_the_llm_provider_protocol() -> None:
    provider: LLMProvider = _provider()  # a type error here would fail mypy

    assert provider is not None


def test_generate_returns_a_normalized_response() -> None:
    client = _FakeClient()

    response = asyncio.run(_provider(client).generate(LLMRequest(user_prompt="plan")))

    assert response.content == '{"scenes":[]}'
    assert response.provider == "openrouter"
    assert response.model == MODEL
    assert response.usage.total_tokens == 15
    assert response.latency >= 0


def test_a_request_model_overrides_the_default() -> None:
    client = _FakeClient()

    asyncio.run(_provider(client).generate(LLMRequest(user_prompt="plan", model="openai/gpt-4o")))

    assert client.requests[0][1] == "openai/gpt-4o"


def test_generate_retries_a_transient_failure() -> None:
    class _Flaky(_FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        async def complete(self, request: LLMRequest, *, model: str) -> RawCompletion:
            self.calls += 1
            if self.calls == 1:
                raise ProviderUnavailableError("503")
            return await super().complete(request, model=model)

    client = _Flaky()

    response = asyncio.run(_provider(client).generate(LLMRequest(user_prompt="plan")))

    assert client.calls == 2
    assert response.content == '{"scenes":[]}'


def test_models_lists_the_catalogue() -> None:
    assert asyncio.run(_provider(_FakeClient(models=[MODEL, "x/y"])).models()) == [MODEL, "x/y"]


def test_count_tokens_estimates_without_an_endpoint() -> None:
    """OpenRouter has no counting API, so this is an approximation."""
    provider = _provider()

    assert asyncio.run(provider.count_tokens("")) == 0
    assert asyncio.run(provider.count_tokens("a" * 400)) == 100


def test_health_is_ok_when_reachable() -> None:
    health = asyncio.run(_provider().health_check())

    assert health.status is HealthStatus.OK
    assert MODEL in health.detail


def test_health_fails_when_the_api_rejects_us() -> None:
    health = asyncio.run(
        _provider(_FakeClient(outcome=AuthenticationError("bad key"))).health_check()
    )

    assert health.status is HealthStatus.FAIL


def test_health_warns_without_an_api_key() -> None:
    provider = OpenRouterProvider(OpenRouterSettings(api_key=None))

    health = asyncio.run(provider.health_check())

    assert health.status is HealthStatus.WARN
    assert "AIVF_OPENROUTER_API_KEY" in health.detail


def test_generating_without_an_api_key_fails_cleanly() -> None:
    provider = OpenRouterProvider(OpenRouterSettings(api_key=None))

    with pytest.raises(AuthenticationError, match="not configured"):
        asyncio.run(provider.generate(LLMRequest(user_prompt="plan")))


# --- configuration ---------------------------------------------------------


def test_the_documented_environment_variables_are_honoured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIVF_DIRECTOR_PROVIDER", "openrouter")
    monkeypatch.setenv("AIVF_OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("AIVF_OPENROUTER_MODEL", MODEL)

    settings = load_settings()

    assert settings.director_provider == "openrouter"
    assert settings.openrouter.api_key is not None
    assert settings.openrouter.api_key.get_secret_value() == "sk-or-test"
    assert settings.openrouter.model == MODEL


def test_the_default_model_is_deepseek() -> None:
    assert Settings().openrouter.model == MODEL


def test_the_director_does_not_default_to_openrouter() -> None:
    """The director must run without an OpenRouter key being configured."""
    assert Settings().director_provider == ""


def test_a_blank_api_key_reads_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIVF_OPENROUTER_API_KEY", "   ")

    assert load_settings().openrouter.api_key is None


def test_the_api_key_is_never_serialized() -> None:
    settings = Settings(openrouter_api_key=SecretStr("sk-or-secret"))

    assert "sk-or-secret" not in str(settings.model_dump())


def test_the_general_provider_settings_are_untouched() -> None:
    """Sprint 024 must not disturb the story pipeline's own provider."""
    settings = Settings()

    assert settings.provider.provider == "gemini"
    assert settings.provider.model == "gemini-3.5-flash"


# --- factory wiring --------------------------------------------------------


def test_openrouter_is_a_supported_provider() -> None:
    assert "openrouter" in ProviderFactory.supported_providers()
    assert "gemini" in ProviderFactory.supported_providers()


def test_the_director_uses_gemini_by_default() -> None:
    """Restored: the director shares the story pipeline's provider."""
    provider = ProviderFactory.create_director(
        Settings(provider=ProviderSettings(api_key=SecretStr("k")))
    )

    assert isinstance(provider, GeminiProvider)


def test_the_director_needs_no_openrouter_key() -> None:
    settings = Settings(provider=ProviderSettings(api_key=SecretStr("k")))

    assert settings.openrouter.api_key is None
    assert isinstance(ProviderFactory.create_director(settings), GeminiProvider)


def test_openrouter_is_still_available_when_asked_for() -> None:
    """Backward compatible: an operator who wants it can still select it."""
    settings = Settings(director_provider="openrouter", openrouter_api_key=SecretStr("k"))

    assert isinstance(ProviderFactory.create_director(settings), OpenRouterProvider)


def test_the_director_can_be_pointed_back_at_gemini() -> None:
    settings = Settings(director_provider="gemini")

    assert isinstance(ProviderFactory.create_director(settings), GeminiProvider)


def test_an_unknown_director_provider_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="unsupported director provider"):
        ProviderFactory.create_director(Settings(director_provider="not-a-provider"))


def test_the_director_model_comes_from_openrouter_when_selected() -> None:
    assert ProviderFactory.director_model(Settings(director_provider="openrouter")) == MODEL


def test_the_director_model_defaults_to_the_gemini_override() -> None:
    settings = Settings()

    assert ProviderFactory.director_model(settings) == settings.provider.director_model


def test_the_director_model_falls_back_to_the_gemini_override() -> None:
    settings = Settings(director_provider="gemini")

    assert ProviderFactory.director_model(settings) == settings.provider.director_model


def test_the_general_factory_still_builds_gemini() -> None:
    assert isinstance(ProviderFactory.create(Settings()), GeminiProvider)


def test_the_general_factory_can_also_select_openrouter() -> None:
    settings = Settings.model_validate(
        {"provider": {"provider": "openrouter"}, "openrouter_api_key": "k"}
    )

    assert isinstance(ProviderFactory.create(settings), OpenRouterProvider)


def test_the_director_service_is_built_on_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    """End of the wiring: `director` talks to Gemini again.

    Restored after the director was routed through OpenRouter. An OpenRouter
    key being present must not be enough to pull the director onto it.
    """
    monkeypatch.setenv("AIVF_OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("AIVF_PROVIDER__API_KEY", "gemini-test")
    settings = load_settings()

    service = DirectorService.from_settings(settings)

    assert isinstance(service._provider, GeminiProvider)


def test_the_director_service_can_still_be_routed_to_openrouter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backward compatible: the Sprint 024 route survives as an opt-in."""
    monkeypatch.setenv("AIVF_DIRECTOR_PROVIDER", "openrouter")
    monkeypatch.setenv("AIVF_OPENROUTER_API_KEY", "sk-or-test")
    settings = load_settings()

    service = DirectorService.from_settings(settings)

    assert isinstance(service._provider, OpenRouterProvider)
    assert service._model == MODEL
