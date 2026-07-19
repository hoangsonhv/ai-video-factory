# CHANGELOG

**Purpose:** The human-readable, chronological record of notable changes to AI Video Factory across releases. It tells users and contributors what changed, when, and why — distinct from git history (mechanical) and `03_ROADMAP.md` (forward-looking intent).

**Owner:** Technical Lead.

**When to update:** On every release/version bump, and by accumulating entries under `[Unreleased]` as meaningful changes land (new stage, new provider, behavior change, breaking change). At release time, `[Unreleased]` is renamed to the version with a date.

**Format:** Based on [Keep a Changelog](https://keepachangelog.com/); versions follow [Semantic Versioning](https://semver.org/). Change groups: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

---

## [Unreleased]

### Added
- **Sprint 009 — Pipeline Orchestrator, Phase 1 (ADR-019):**
  - `PipelineRunner` (`infrastructure/pipeline/`) composing the existing idea/outline/chapter/image-prompt generators — sequential, persists each output immediately, stops on the first failure; one shared provider + prompt service.
  - `PipelineRequest` / `PipelineResult` typed models; progress via an injected `on_stage` callback.
  - CLI `ai-video-factory generate --topic --style --platform [--chapters]` → Rich progress (`[1/4] …`) + summary; writes `output/{ideas,story_outline,chapter,image_prompts}.json`. No image generation.
  - 3 new integration tests with a stage-aware fake provider (all outputs, stop-on-failure, `generate` CLI); no real API calls.
- **Sprint 008 — Image Provider Layer (ADR-018):**
  - `ImageProvider` Protocol (`generate`, `health_check`, `models`) with `ImageGenerationRequest` / `ImageGenerationResponse` (`infrastructure/providers/image/base/`).
  - `GeminiImagenProvider` over google-genai Imagen behind an `ImagenClient` seam (SDK lazily imported), retrying transient errors once; reuses the shared `AIProviderError`/`RetryPolicy`/`ProviderHealth`.
  - `ImageProviderFactory.create(settings, storage)` — config-driven selection; image API key falls back to the LLM key.
  - `ImageStorage` (`infrastructure/media/`) → sequential PNGs (`image_001.png`, …) in `output/images/`.
  - Configuration: `ImageProviderSettings` (provider/api_key/model/timeout/retry_count).
  - CLI `ai-video-factory image --input <image_prompts.json>` → Rich progress bar + summary; saves images.
  - 20 new tests (request/response models, storage, Imagen provider with a fake client, factory, CLI); no real API calls.
- **Sprint 007 — Image Prompt Generator (ADR-017):**
  - Domain value object `ImagePrompt` (scene_number, prompt, negative_prompt, aspect_ratio, style, camera, lighting, character_reference, environment, seed?).
  - `infrastructure/story/`: `ImagePromptGenerator` (prompt + configured `LLMProvider` via `ProviderFactory`, JSON mode, retry once), `parse_image_prompts` (injects project-level style/aspect_ratio), `ImagePromptParseError`, `read_chapter`, `write_image_prompts_json`.
  - CLI `ai-video-factory image-prompt --chapter <path> [--style --aspect-ratio --count --language]` → Rich table + `output/image_prompts.json`. Produces prompt text only — no images generated.
  - 19 new tests (image-prompt model, parser, chapter reader, generator with a fake provider, CLI); no real API calls.
- **Sprint 006 — Chapter Generator (ADR-016):**
  - Domain value object `StoryChapter` (title, content, estimated_duration_seconds).
  - `infrastructure/story/`: `ChapterGenerator` (prompt + configured `LLMProvider` via `ProviderFactory`, JSON mode, retry once), `parse_chapter` with deterministic `estimate_duration_seconds` (computed from content, not LLM-trusted), `ChapterParseError`, `read_outline`, `write_chapter_json`.
  - CLI `ai-video-factory chapter --outline <path> [--language]` → Rich chapter view + `output/chapter.json`.
  - 20 new tests (chapter model, parser/estimator, outline reader, generator with a fake provider, CLI); no real API calls.
- **Sprint 005 — Story Outline Generator (ADR-015):**
  - Domain value objects `StoryOutline` (title, genre, world_setting, cultivation_system, main_character, supporting_characters, antagonist, story_arc, ending, chapter_outlines) and `ChapterOutline` (chapter_number, title, summary, cliffhanger).
  - `infrastructure/story/`: `OutlineGenerator` (prompt + configured `LLMProvider` via `ProviderFactory`, JSON mode, parse + validate, retry once), `parse_outline` (chapter-count + required-field + non-empty validation), `OutlineParseError`, `read_idea`, `write_outline_json`.
  - CLI `ai-video-factory outline --idea <path> [--index --chapters --duration --language]` → Rich tables + `output/story_outline.json`.
  - Shared UTF-8-safe presenter helper `console_io.emit_renderable` (idea presenter reuses it).
  - 22 new tests (outline models, parser, idea reader, generator with a fake provider, CLI); no real API calls.
- **Sprint 004 — Story Idea Generator (ADR-014):**
  - Domain value objects `IdeaBrief` (topic/style/target_platform/language) and `StoryIdea` (title/hook/summary/tags).
  - `infrastructure/story/`: `IdeaGenerator` (prompt + configured `LLMProvider` via `ProviderFactory`, JSON mode, parse + validate, retry once), `parse_ideas`, `IdeaParseError`, `write_ideas_json`.
  - CLI `ai-video-factory idea --topic --style --platform [--language]` → Rich table + `output/ideas.json`.
  - 17 new tests (models, parser, generator with a fake provider, CLI); no real API calls.
- **Sprint 003 — Prompt Engine (ADR-013):**
  - `infrastructure/prompts/`: `PromptLoader` (load + cache + `PromptNotFoundError`), `PromptRenderer` (Jinja2, `StrictUndefined`), `PromptValidator` (exists + syntax + required variables), `PromptService` (`render`, `validate`, `list_prompts`).
  - Prompt error hierarchy: `PromptError → PromptNotFoundError`, `PromptValidationError`, `PromptRenderError`.
  - Prompt templates under the configurable root `prompts/`: `story/idea.md`, `story/outline.md`, `story/chapter.md`, `story/scene.md`, `image/image_prompt.md` — no prompt text in Python.
  - Configuration: `PromptSettings.root` (default `prompts/`, env `AIVF_PROMPTS__ROOT`); `jinja2` runtime dependency.
  - CLI: `factory prompt list`, `prompt show <name>`, `prompt validate`, `prompt render <name> --var k=v` (UTF-8-safe raw output).
  - 26 new tests (loader, renderer, validator, service incl. shipped templates, CLI).
- **Sprint 002 — AI Provider Layer:** the single, vendor-neutral way the system talks to LLM providers (ADR-012).
  - `LLMProvider` Protocol (`generate`, `health_check`, `count_tokens`, `models`) with strongly typed `LLMRequest`, `LLMResponse`, `TokenUsage`, `RawCompletion`, `ProviderHealth`.
  - Provider error hierarchy: `AIProviderError` → `AuthenticationError`, `RateLimitError`, `TimeoutError`, `ProviderUnavailableError`, `InvalidResponseError` (extends the existing `ProviderError` tree).
  - `RetryPolicy` — exponential backoff retrying only 429/503/timeout; configurable per-request timeout.
  - `GeminiProvider` (first provider) over the official `google-genai` SDK, isolated behind a `GeminiClient` seam (SDK lazily imported); API key read from settings.
  - `ProviderFactory.create()` — config-driven provider selection.
  - `ProviderSettings` (`provider`, `api_key` as `SecretStr`, `model`, `timeout`, `retry_count`); `google-genai` runtime dependency.
  - `doctor` now checks the AI provider (API key configured + reachable), reporting OK/WARN/FAIL; diagnostics status is tri-state via `shared/health.HealthStatus`.
  - 35 new tests (models, errors, retry, Gemini via a fake client, factory) — no real API calls.
- **Sprint 001.5 — Foundation Review Fix:**
  - `.editorconfig` (UTF-8, LF, 4-space indent, trim trailing whitespace, final newline; Markdown/Makefile/YAML overrides).
  - `Makefile` targets: `install`, `sync`, `lint`, `format`, `typecheck`, `test`, `doctor`, `run`, `clean`, `hooks`.
  - `.pre-commit-config.yaml` with ruff check, ruff format, mypy, and a manual-stage pytest hook (local hooks via `uv run`); `pre-commit` added to dev extras.
  - `.gitkeep` placeholders for `logs/`, `output/`, `data/`.
- **Sprint 001 — Project Foundation:**
  - `src/` layout with Clean Architecture layer packages under `src/ai_video_factory/` (`domain`, `application`, `infrastructure`, `interface`, `shared`).
  - Configuration: typed `Settings` tree via `pydantic-settings` with `.env` support and fail-fast `ConfigurationError` (env prefix `AIVF_`, `__` nesting).
  - Logging: Rich console + rotating-file handlers, config-driven, idempotent setup.
  - Exceptions: `AppError` hierarchy (`DomainError`, `ApplicationError`, `InfrastructureError` → `ProviderError`/`PersistenceError`/`MediaError`, `ConfigurationError`).
  - CLI: Typer application with `version` and `doctor` commands and a Rich diagnostics presenter; `factory` console script and `python -m ai_video_factory`.
  - Doctor diagnostics: Python version, FFmpeg availability, writable output folder, configuration loading, SQLite connectivity.
  - Tooling: Ruff (lint + format), MyPy (strict), Pytest — configured and passing (30 tests).
  - Project scaffolding: `pyproject.toml` (hatchling, src layout), `.gitignore`, `.env.example`, `README.md`.
- ADR-011 (src layout + foundation tooling: Typer, pydantic-settings, Rich, Ruff-only formatter).
- Architecture Document (canonical) defining Clean Architecture with four inward-pointing layers (Domain, Application, Infrastructure, Interface) plus `shared`.
- Complete project documentation set in `docs/`:
  `00_PROJECT`, `01_AI_CONTEXT`, `03_ROADMAP`, `04_DECISIONS`, `05_CONVENTIONS`, `06_PROMPT_RULES`, `07_WORKFLOW`, `08_ENVIRONMENT`, `09_PRODUCT_VISION`, `10_TECH_DEBT`, `11_BACKLOG`, `12_PROJECT_STATE`, `13_SESSION_HANDOFF`, `CHANGELOG`.
- Architecture Decision Records ADR-001 through ADR-010 (CLI-first, Python 3.13 async, SQLite, no FastAPI, provider abstraction, enforced inward deps, Pydantic v2/entity≠ORM, config-driven fail-fast, resumable checkpoints, structured logging).
- Roadmap Sprint 000 → 020 to v1.0 with per-sprint goals, deliverables, acceptance criteria, and dependencies.
- Initial backlog (Critical/High/Medium/Low/Post-1.0) and technical-debt register (TD-001 … TD-006).

### Changed
- `prompts/story/idea.md` rewritten to generate multiple story ideas as JSON (variables `topic, style, target_platform, language, count`); two Sprint 003 prompt tests updated to match.
- `prompts/story/outline.md` rewritten to generate a full `StoryOutline` as JSON (variables `idea_title, idea_hook, idea_summary, target_duration, chapter_count, language`).
- `prompts/story/chapter.md` rewritten to generate narration prose as JSON `{title, content}` from the outline fields.
- `prompts/image/image_prompt.md` rewritten to generate a JSON `{image_prompts:[…]}` array of cinematic image prompts from the chapter (variables `chapter_title, chapter_content, style, aspect_ratio, count, language`).

### Deprecated
- _None._

### Removed
- _None._

### Fixed
- Story generators no longer fail with "provider returned invalid JSON" on thinking-capable models: raised `max_output_tokens` to 8192 for the idea/outline/chapter/image-prompt generators (a small cap truncated the JSON), and added lenient JSON parsing (`json_extract.loads_json`) that tolerates Markdown code fences.
- Chapter generation robustness: the chapter prompt now asks for a bounded ~180–300 word short-video narration (previously "the complete story", which overran the token budget and truncated the JSON); the chapter parser tolerates unescaped control characters (long-prose newlines, `strict=False`) and double-encoded JSON, and surfaces the actual `JSONDecodeError` detail instead of a generic message; the raw model response is logged and saved to `output/debug/chapter_raw_response.txt` for diagnosis.
- Tests are now isolated from a local `.env` file (which may hold a real API key), so no test can accidentally hit a live provider.

### Changed
- Expanded `.gitignore` (tooling caches, virtualenvs, coverage, logs, `output/*` and `data/*` with `.gitkeep` negations, `.env`, IDE/OS files).
- Rewrote `CLAUDE.md` to define project role, architecture rules, sprint rules, coding rules, and review rules.

### Removed
- Runtime artifacts removed from the working tree (`__pycache__`, `*.pyc`, `*.db`, `*.sqlite`, log files); the `logs/`, `output/`, and `data/` folders are preserved via `.gitkeep`.

### Fixed
- CLI raw text output (`prompt show`/`prompt render`) no longer crashes on legacy Windows (cp1252) consoles when the content contains non-ASCII characters (e.g. Vietnamese, Chinese); it is now written as UTF-8 bytes.

### Security
- Established the invariant that secrets are handled as `SecretStr`, never logged or persisted, with an active redaction filter (ADR-008, ADR-010).

---

## Release History

_(No versioned releases yet. The first tagged release will be `0.1.0` at the end of Sprint 006 — foundation complete.)_

---

## Planned Version Milestones (from `03_ROADMAP.md`)

| Version | Milestone | Target |
|---|---|---|
| `0.1.0` | Foundation (domain, app, persistence, config, logging, CLI, DI) | End of Sprint 006 |
| `0.2.0` | First stage end-to-end (Story) | End of Sprint 008 |
| `0.5.0` | All six stages exist | End of Sprint 013 |
| `0.9.0` | Full pipeline resumable & observable | End of Sprint 019 |
| `1.0.0` | Release (Idea → MP4 via CLI) | End of Sprint 020 |

> These are planned targets, not releases. Entries move into "Release History" only when a version is actually tagged.

---

### Example release entry (format to follow at first tag)

```
## [0.1.0] — 2026-08-XX

### Added
- Package skeleton with enforced layer boundaries (import-linter).
- Domain core: entities, value objects, enums, DomainError hierarchy.
- Workflow engine: Pipeline, PipelineStep, StageResult with checkpoint semantics.
- SQLite persistence via SQLAlchemy 2 + Alembic; entity⇄ORM mappers; UnitOfWork.
- Config-driven settings tree with fail-fast validation.
- Structured, correlated logging with secret redaction.
- CLI (generate/resume/status/render) + composition root + provider registry.

### Notes
- No AI provider stages yet (first stage arrives in 0.2.0).
```
