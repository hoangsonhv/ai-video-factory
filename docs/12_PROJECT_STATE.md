# 12 — PROJECT STATE (Single Source of Truth)

> **⚠ READ THIS FILE FIRST before continuing any development.**
> This is the authoritative, always-current snapshot of the project. Where this file and any other document disagree about *current state*, this file wins. Where this file and the Architecture Document disagree about *structure*, the Architecture Document wins — and this file must be corrected.

**Purpose:** The one place that answers "where are we right now?" — version, sprint, what's done, what's in progress, what's next, what's blocked, and the live configuration of providers and modules. Every session begins here.

**Owner:** Technical Lead (updated by whoever advances the work).

**When to update:** At the **start and end of every working session** and at every sprint boundary. Keep it terse and factual. Keep `01_AI_CONTEXT.md` consistent with it.

**Last updated:** 2026-07-19

> **Sprint numbering note:** The executing plan from the Lead labels the foundation work **"Sprint 001 — Project Foundation"** (bootstrap + config + logging + CLI + exceptions + tests + tooling). This differs from the roadmap's Sprint 001 ("Domain Core"); the foundation was implemented per the Lead's explicit spec. Roadmap re-alignment, if desired, is the Lead's call.

---

## 1. Current Version

`0.1.0-dev` (foundation delivered; targeting `0.1.0` tag at end of the foundation milestone)

## 2. Current Sprint

**Sprint 009 — Pipeline Orchestrator (Phase 1) — DELIVERED** (idea → outline → chapter → image prompts, one command; see also `03_ROADMAP.md`)

## 3. Completed

- Architecture Document (canonical) — **done**.
- Full documentation set in `docs/` (`00`–`13`, `CHANGELOG`) — **done**.
- ADR-001 … ADR-019 recorded — **done**.
- **Sprint 009 — Pipeline Orchestrator (Phase 1) — done:**
  - `PipelineRunner` (`infrastructure/pipeline/`) composes the existing four generators — no new business logic. Sequential stages; each output persisted immediately; any failure stops the run (earlier outputs kept). One shared provider + prompt service across all stages.
  - `PipelineRequest` / `PipelineResult` typed models; progress via an injected `on_stage` callback (runner stays Rich-free).
  - CLI `ai-video-factory generate --topic --style --platform [--chapters]` → Rich progress (`[1/4] …`) + summary; writes `output/{ideas,story_outline,chapter,image_prompts}.json`. Graceful exit 1 on failure.
  - **No image generation / TTS / subtitle / ffmpeg / upload** (strict rule honored).
  - Tests: 198 total (3 new integration — runner produces all outputs, stop-on-failure, `generate` CLI end-to-end, with a stage-aware fake provider); no real API calls.
  - Verified end-to-end against the live API (all four files produced). Ruff, MyPy (strict), Pytest all green.
- **Sprint 008 — Image Provider Layer — done:**
  - `ImageProvider` Protocol (`generate`, `health_check`, `models`) + `ImageGenerationRequest` / `ImageGenerationResponse` in `infrastructure/providers/image/base/`.
  - `GeminiImagenProvider` (google-genai Imagen) behind an `ImagenClient` seam (SDK lazily imported); saves via `ImageStorage`, retries transient errors once. Reuses the shared `AIProviderError`/`RetryPolicy`/`ProviderHealth`/`HealthStatus`.
  - `ImageProviderFactory.create(settings, storage)` — config-driven, no hardcoded provider; image API key falls back to the LLM key.
  - `ImageStorage` (`infrastructure/media/`) writes sequential `image_001.png`, `image_002.png`, … to `output/images/`.
  - Config: `ImageProviderSettings` (provider/api_key/model/timeout/retry_count).
  - CLI `ai-video-factory image --input <image_prompts.json>` → Rich progress bar + summary; graceful exit 1.
  - Tests: 189 total (20 new — request/response models, storage, Imagen provider with fake client, factory, CLI); no real API calls.
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 007 — Image Prompt Generator — done:**
  - Domain value object `ImagePrompt` (scene_number, prompt, negative_prompt, aspect_ratio, style, camera, lighting, character_reference, environment, seed?).
  - `infrastructure/story/`: `ImagePromptGenerator` (renders `image/image_prompt.md`, provider from `ProviderFactory` in JSON mode, parse + retry once), `parse_image_prompts` (injects project-level style/aspect_ratio), `ImagePromptParseError`, `read_chapter`, `write_image_prompts_json`.
  - Prompt `image/image_prompt.md` rewritten to a JSON `{image_prompts:[…]}` template (vars: chapter_title, chapter_content, style, aspect_ratio, count, language).
  - CLI `ai-video-factory image-prompt --chapter <path> [--style --aspect-ratio --count --language]` → Rich table + `output/image_prompts.json`; graceful exit 1.
  - Text only — no images generated (ADR-017).
  - Tests: 169 total (19 new — image-prompt model, parser, chapter reader, generator with fake provider, CLI); no real API calls.
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 006 — Chapter Generator — done:**
  - Domain value object `StoryChapter` (title, content, estimated_duration_seconds).
  - `infrastructure/story/`: `ChapterGenerator` (renders `story/chapter.md` from the outline, provider from `ProviderFactory` in JSON mode, parse + retry once), `parse_chapter` + `estimate_duration_seconds` (computed, not LLM-trusted), `ChapterParseError`, `read_outline`, `write_chapter_json`.
  - Prompt `story/chapter.md` rewritten to a JSON `{title, content}` template driven by the outline fields.
  - CLI `ai-video-factory chapter --outline <path> [--language]` → Rich chapter view + `output/chapter.json`; graceful exit 1 on any `AppError`.
  - Interpretation: the whole outline is rendered as one narration chapter (single input arg, single output); recorded in ADR-016.
  - Tests: 150 total (20 new — chapter model, parser/estimator, outline reader, generator with fake provider, CLI); no real API calls.
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 005 — Story Outline Generator — done:**
  - Domain value objects `StoryOutline` (title, genre, world_setting, cultivation_system, main_character, supporting_characters, antagonist, story_arc, ending, chapter_outlines) and `ChapterOutline` (chapter_number, title, summary, cliffhanger).
  - `infrastructure/story/`: `OutlineGenerator` (renders `story/outline.md`, provider from `ProviderFactory` in JSON mode, parse + validate, retry once), `parse_outline` (chapter-count + required-field + non-empty validation), `OutlineParseError`, `read_idea` (select from ideas JSON), `write_outline_json`.
  - Prompt `story/outline.md` rewritten to a JSON `StoryOutline` template (vars: idea_title, idea_hook, idea_summary, target_duration, chapter_count, language).
  - CLI `ai-video-factory outline --idea <path> [--index --chapters --duration --language]` → Rich tables + `output/story_outline.json`; graceful exit 1 on any `AppError`.
  - Shared `console_io.emit_renderable` (UTF-8-safe) extracted; `idea_presenter` reuses it.
  - Tests: 130 total (22 new — outline models, parser, idea reader, generator with fake provider, CLI); no real API calls.
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 004 — Story Idea Generator — done:**
  - Domain value objects `IdeaBrief` (topic/style/target_platform/language) and `StoryIdea` (title/hook/summary/tags) in `domain/value_objects/idea.py` (first domain content).
  - `infrastructure/story/`: `IdeaGenerator` (renders `story/idea.md`, calls `LLMProvider` from `ProviderFactory` in JSON mode, parses + validates, retries once), `parse_ideas`, `IdeaParseError`, `write_ideas_json`.
  - Prompt `story/idea.md` evolved to a multi-idea JSON template (vars: topic, style, target_platform, language, count).
  - CLI `ai-video-factory idea --topic --style --platform [--language]` → Rich table + `output/ideas.json`; graceful exit 1 on any `AppError` (e.g. missing key).
  - Tests: 108 total (17 new — models, parser, generator with fake provider, CLI; 2 Sprint 003 prompt tests updated for the new idea.md vars); no real API calls.
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 003 — Prompt Engine — done:**
  - Prompt templates under configurable root `prompts/` (`story/{idea,outline,chapter,scene}.md`, `image/image_prompt.md`) — no prompt text in Python.
  - `infrastructure/prompts/`: `PromptLoader` (load + cache + `PromptNotFoundError`), `PromptRenderer` (Jinja2, `StrictUndefined`), `PromptValidator` (exists + syntax + required vars), `PromptService` (`render`, `validate`, `list_prompts`).
  - Errors: `PromptError → PromptNotFoundError/PromptValidationError/PromptRenderError` (extend `InfrastructureError`).
  - Config: `PromptSettings.root` (default `prompts/`, env `AIVF_PROMPTS__ROOT`).
  - CLI: `prompt list` / `prompt show <name>` / `prompt validate` / `prompt render <name> --var k=v` (UTF-8-safe raw output).
  - Tests: 91 total (26 new — loader, renderer, validator, service incl. shipped templates, CLI).
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 002 — AI Provider Layer — done:**
  - LLM provider contract in `infrastructure/providers/base/`: `LLMProvider` Protocol (`generate`, `health_check`, `count_tokens`, `models`); models `LLMRequest`, `LLMResponse`, `TokenUsage`, `RawCompletion`, `ProviderHealth`.
  - Provider error hierarchy (`AIProviderError` → `AuthenticationError`, `RateLimitError`, `TimeoutError`, `ProviderUnavailableError`, `InvalidResponseError`) extending the `AppError`/`ProviderError` tree.
  - `RetryPolicy` (exponential backoff, retries only 429/503/timeout); configurable per-request timeout via `asyncio.wait_for`.
  - `GeminiProvider` (first provider) over the official `google-genai` SDK, isolated behind a `GeminiClient` seam (SDK lazily imported); API key read from settings.
  - `ProviderFactory.create()` — config-driven provider selection (unknown provider → `ConfigurationError`).
  - Configuration: `ProviderSettings` (`provider`, `api_key` as `SecretStr`, `model`, `timeout`, `retry_count`).
  - `doctor` gains an AI-provider health check returning OK/WARN/FAIL (WARN when no key); diagnostics now tri-state via `shared/health.HealthStatus`.
  - Tests: 65 total (35 new — models, errors, retry, Gemini with a fake client, factory, settings, diagnostics); no real API calls.
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 001.5 — Foundation Review Fix — done:**
  - `.gitignore` expanded (caches, venvs, coverage, logs, `output/*`/`data/*` with `.gitkeep` negations, `.env`, IDE/OS files).
  - `.gitkeep` placeholders in `logs/`, `output/`, `data/`; runtime artifacts removed from the working tree (folders preserved).
  - `CLAUDE.md` rewritten: project role, architecture rules, sprint rules, coding rules, review rules, hard "do not" list.
  - `.editorconfig` (UTF-8, LF, 4-space, trim trailing whitespace, final newline; Markdown/Makefile/YAML overrides).
  - `Makefile` (install, sync, lint, format, typecheck, test, doctor, run, clean, hooks).
  - `.pre-commit-config.yaml` (ruff check, ruff format, mypy; pytest as a manual stage); `pre-commit` added to dev extras.
  - Validation: Ruff, MyPy, Pytest (30) all green; `factory version`/`doctor` run.
- **Sprint 001 — Project Foundation — done:**
  - `src/` layout with Clean Architecture layer packages (`domain`, `application`, `infrastructure`, `interface`, `shared`) under `src/ai_video_factory/` (ADR-011).
  - Configuration: typed `Settings` tree via `pydantic-settings`, `.env` support, fail-fast `ConfigurationError`.
  - Logging: Rich console + rotating file, config-driven, idempotent.
  - Exceptions: `AppError` hierarchy (§7) in `errors.py`.
  - CLI: Typer app with `version` and `doctor` commands + Rich presenter.
  - Doctor checks: Python version, FFmpeg, writable output folder, config loading, SQLite connectivity.
  - Tests: 30 pytest tests (errors, settings, logging, diagnostics, CLI).
  - Tooling: Ruff (lint + format), MyPy strict, Pytest — all green.

## 4. In Progress

- None. Awaiting the next Sprint specification from the Lead.

## 5. Current Branch

`feat/sprint009-pipeline-orchestrator`. `main` is protected.

## 6. Architecture Version

**1.0** — matches the Architecture Document. No deviations.

## 7. Providers (live configuration)

| Stage | Port | Active driver | Adapter | Status |
|---|---|---|---|---|
| Story | `StoryGenerator` | — | `OpenAiStoryGenerator` | planned (Sprint 008) |
| Scene | `SceneBuilder` | — | `LlmSceneBuilder` | planned (Sprint 009) |
| Image | `ImageProvider` | — | `ReplicateImageProvider` | planned (Sprint 010) |
| Voice | `VoiceProvider` | — | `ElevenLabsVoiceProvider` | planned (Sprint 011) |
| Subtitle | `SubtitleProvider` | — | `WhisperSubtitleProvider` | planned (Sprint 012) |
| Video | `VideoComposer` | — | `FfmpegVideoComposer` | planned (Sprint 013) |
| Persistence | `ProjectRepository`, `UnitOfWork` | `sqlite` | `SqlAlchemyProjectRepository` | planned (Sprint 003) |

**AI provider layers (infrastructure):**

| Capability | Contract | Active driver | Adapter | Status |
|---|---|---|---|---|
| LLM completion (Sprint 002) | `LLMProvider` (Protocol) | `gemini` | `GeminiProvider` (`google-genai`) | **implemented** |
| Image generation (Sprint 008) | `ImageProvider` (Protocol) | `gemini_imagen` | `GeminiImagenProvider` (`google-genai` Imagen) | **implemented** |

Future drivers plug in by registering a builder in the respective factory (`ProviderFactory` / `ImageProviderFactory`); no existing code changes (ADR-005).

**Story generators (Sprint 004–007):** `IdeaGenerator`, `OutlineGenerator`, `ChapterGenerator`, `ImagePromptGenerator` (infrastructure/story). **Image generation (Sprint 008):** `image` CLI → PNGs in `output/images/`. **Pipeline (Sprint 009):** `PipelineRunner` composes the four generators; `generate` runs the whole chain in one command. File-based chain: `ideas.json → story_outline.json → chapter.json → image_prompts.json` (→ `output/images/*.png` via `image`).

## 8. Modules (layer readiness)

| Layer | Package | Status |
|---|---|---|
| Domain | `src/ai_video_factory/domain/` | **value_objects (IdeaBrief, StoryIdea, StoryOutline, ChapterOutline, StoryChapter, ImagePrompt)** implemented |
| Application | `src/ai_video_factory/application/` | package marker only (populated later) |
| Infrastructure | `src/ai_video_factory/infrastructure/` | **config, logging, diagnostics, providers (llm + image), prompts, story, media, pipeline** implemented |
| Interface | `src/ai_video_factory/interface/` | **cli (version/doctor/prompt/idea/outline/chapter/image-prompt/image/generate), presenters** implemented |
| Shared | `src/ai_video_factory/shared/` | **health** implemented |

## 9. Current Tasks

- [x] `PipelineRunner` composing the four existing generators (no duplicated logic).
- [x] Sequential stages, persist-after-each, stop-on-failure; shared provider + prompts.
- [x] `PipelineRequest`/`PipelineResult`; `on_stage` progress callback.
- [x] CLI `generate` (Rich progress `[n/4]` + summary); graceful error handling.
- [x] Integration tests with a stage-aware fake provider (all outputs / stop-on-failure / CLI).
- [x] Ruff + MyPy(strict) + Pytest passing (198 tests); verified live end-to-end.

## 10. Next Tasks

- Await next Sprint spec from the Lead. `generate` runs idea→image-prompts; wiring in image generation (Phase 2) is the natural next step, but **only build when specified**.

## 11. Known Issues

- `factory doctor` reports **FFmpeg: FAIL** on machines without ffmpeg installed (expected — documented runtime dependency, `08_ENVIRONMENT.md`). Not a code defect.
- `RealGeminiClient` (live `google-genai` calls) is not exercised by the test suite by design (tests use a fake client — no real API calls). It is covered manually via `doctor` when a key is configured.
- import-linter is not yet wired as an automated gate (layer boundaries upheld by construction/review). Tracked for a later tooling pass.

## 12. Blocked By

- Nothing. Sprint 000 has no external dependencies.

## 13. Roadmap Progress

```
[██□□□□□□□□□□□□□□□□□□□]  Foundation delivered   (~10%)
Milestones: 0.1.0 (foundation) · 0.2.0 (first stage e2e) · 0.5.0 (all stages) · 0.9.0 (resumable) · 1.0.0 (release)
```

- Foundation (Sprint 001 per Lead spec) delivered.
- Next milestone: first pipeline stage end-to-end (requires Domain Core first).

## 14. Important Decisions (quick reference)

| ADR | Decision | Impact on current work |
|---|---|---|
| 001 | CLI first, no Web UI | Only build CLI delivery |
| 002 | Python 3.13, async-first | All I/O async from the start |
| 003 | SQLite | Persistence target for Sprint 003 |
| 004 | No FastAPI for MVP | Do not add HTTP layer |
| 005 | Provider abstraction via ports/drivers | Every AI capability behind a port |
| 006 | Enforced inward dependencies | import-linter is a Sprint 000 gate |
| 008 | Config-driven, fail-fast | Config tree in Sprint 004 |
| 009 | Resumable checkpoints | Workflow engine in Sprint 002 |

Full records in `04_DECISIONS.md`.

## 15. Project Metrics

| Metric | Value | As of |
|---|---|---|
| Version | 0.1.0-dev | 2026-07-18 |
| Sprint | 009 — Pipeline Orchestrator (Phase 1, delivered) | 2026-07-19 |
| Roadmap progress | ~42% | 2026-07-19 |
| Pipeline | `generate`: idea→outline→chapter→image-prompts (one command) | 2026-07-19 |
| AI providers implemented | 2 (gemini LLM, gemini_imagen) | 2026-07-19 |
| Prompt templates | 5 (story×4, image×1) | 2026-07-19 |
| Tests | 198 passing | 2026-07-19 |
| Open tech-debt items | 6 | 2026-07-19 |
| Gates (Ruff / MyPy / Pytest) | all green | 2026-07-19 |

---

### Update discipline

At every session end, refresh: **Current Sprint, Completed, In Progress, Current Branch, Current/Next Tasks, Known Issues, Blocked By, Roadmap Progress, Metrics, Last updated**. Then update `13_SESSION_HANDOFF.md` and, at sprint close, `01_AI_CONTEXT.md` and `CHANGELOG.md`.
