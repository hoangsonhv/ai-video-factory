# 04 — DECISIONS (Architecture Decision Records)

**Purpose:** The immutable, append-only log of significant technical decisions — what was decided, why, what was rejected, and the consequences. ADRs prevent re-litigating settled choices and explain the *why* behind the architecture to future contributors.

**Owner:** Technical Lead (proposals may come from anyone; the Lead accepts/supersedes).

**When to update:** Whenever a decision with lasting architectural impact is made. **Never edit an accepted ADR's decision** — supersede it with a new ADR and mark the old one `Superseded by ADR-XXX`. Status values: `Proposed`, `Accepted`, `Superseded`, `Deprecated`.

---

## ADR Format

```
### ADR-XXX — <Title>
- Status:
- Date:
- Context:
- Decision:
- Consequences:
- Alternatives considered:
```

---

### ADR-001 — CLI First (No Web UI)
- **Status:** Accepted
- **Date:** 2026-07-18
- **Context:** The MVP audience is a technical operator generating videos in batch. A UI adds surface area, framework coupling, and maintenance cost with no MVP value.
- **Decision:** The only delivery mechanism is a command-line interface. All operations are CLI commands (`generate`, `resume`, `status`, `render`) that invoke application use cases.
- **Consequences:** Fast iteration; scriptable/automatable; the interface layer stays thin. A future Web UI or API can be added as a *sibling* interface adapter over the same use cases without touching the core.
- **Alternatives considered:** Web UI (rejected — premature, heavy); TUI (deferred — CLI sufficient for MVP).

### ADR-002 — Python 3.13, Async-First
- **Status:** Accepted
- **Date:** 2026-07-18
- **Context:** The pipeline is dominated by I/O-bound provider calls (LLM, image, TTS) that benefit from concurrency, plus one CPU/blocking step (ffmpeg). Strong typing is a hard requirement.
- **Decision:** Python 3.13 with an async-first design; all I/O is `async`; blocking work runs off the event loop via `asyncio.to_thread`/subprocess.
- **Consequences:** Efficient per-scene fan-out; modern typing features; requires discipline to never block the loop. Team must be fluent in `asyncio`.
- **Alternatives considered:** Sync + threads (rejected — poor fit for many concurrent provider calls); Go/Rust (rejected — Python's AI ecosystem and team fit win).

### ADR-003 — SQLite for Persistence
- **Status:** Accepted
- **Date:** 2026-07-18
- **Context:** MVP is single-machine, CLI-driven, single-writer. It needs durable, transactional state for checkpoint/resume without operational overhead.
- **Decision:** SQLite via SQLAlchemy 2, with Alembic migrations. Domain entities are kept separate from ORM models (no active record).
- **Consequences:** Zero-ops, embedded, transactional; perfect for resumable single-machine runs. Entity/ORM separation makes a later swap to Postgres a contained infrastructure change.
- **Alternatives considered:** Postgres (rejected for MVP — operational overhead, no multi-writer need yet); flat files/JSON (rejected — no transactions, weak querying).

### ADR-004 — No FastAPI / No HTTP API for MVP
- **Status:** Accepted
- **Date:** 2026-07-18
- **Context:** An HTTP layer implies servers, auth, serialization contracts, and deployment concerns irrelevant to the MVP goal (Idea→MP4 from a terminal).
- **Decision:** No FastAPI, no HTTP API in the MVP/1.0 scope. Delivery is CLI-only.
- **Consequences:** Smaller footprint, faster delivery. Because use cases are framework-agnostic and injected, a FastAPI adapter can later sit beside the CLI with no core changes.
- **Alternatives considered:** FastAPI now (rejected — premature); gRPC (rejected — same reasoning).

### ADR-005 — Replaceable AI Providers via Ports & Drivers
- **Status:** Accepted
- **Date:** 2026-07-18
- **Context:** The domain is stable; AI vendors/models are volatile. The system must swap providers without rewrites.
- **Decision:** One narrow port per capability (`StoryGenerator`, `SceneBuilder`, `ImageProvider`, `VoiceProvider`, `SubtitleProvider`, `VideoComposer`), each owned by the domain and speaking domain language. Concrete adapters live in infrastructure and are selected by a config `driver` key via a provider registry. Cross-cutting concerns (retry, rate limit, cache) are decorator adapters. Substitutability is guaranteed by shared contract tests.
- **Consequences:** New/replaced provider = new adapter + registry entry + config change, no edits to existing code (OCP). Vendor exceptions never leak inward. Slightly more upfront structure.
- **Alternatives considered:** A single monolithic `AIProvider` interface (rejected — violates ISP, couples stages); direct SDK calls in use cases (rejected — non-replaceable, untestable).

### ADR-006 — Clean Architecture with Enforced Inward Dependencies
- **Status:** Accepted
- **Date:** 2026-07-18
- **Context:** The project is long-lived; volatility must be isolated from the stable core.
- **Decision:** Four layers (Domain→Application→Infrastructure→Interface) plus a dependency-free `shared`. Source dependencies point inward only, enforced by import-linter in CI.
- **Consequences:** The core ages slowly; volatile edges are replaceable; the rule is machine-checked so it cannot silently erode. Requires wiring discipline at the composition root.
- **Alternatives considered:** Layered-by-technical-type only (rejected — leaks concerns inward); no enforcement (rejected — architecture drift).

### ADR-007 — Pydantic v2 at Boundaries, Entities Separate from ORM
- **Status:** Accepted
- **Date:** 2026-07-18
- **Context:** Data crossing boundaries (config, DTOs, provider payloads, value objects) must be validated and strongly typed; persistence must not contaminate the domain.
- **Decision:** Pydantic v2 for all boundary data and validated value objects (`frozen=True` where immutable). SQLAlchemy models live only in infrastructure; mappers translate entity⇄ORM.
- **Consequences:** Strong validation and typing; clean domain; explicit mapping cost accepted for isolation.
- **Alternatives considered:** ORM-as-domain / active record (rejected — couples domain to SQLAlchemy); untyped dicts across boundaries (rejected — unsafe).

### ADR-008 — Config-Driven Behavior with Fail-Fast Validation
- **Status:** Accepted
- **Date:** 2026-07-18
- **Context:** Provider selection, concurrency, and environment differences must be changeable without code edits, and misconfiguration must never surface mid-render.
- **Decision:** A single typed Pydantic settings tree with layered precedence (CLI > env > `.env` > file > defaults), validated once at startup; unknown `driver` or invalid values raise `ConfigurationError` before any work begins. Secrets are `SecretStr`, from env/secret files only.
- **Consequences:** Predictable startup failures; safe secret handling; no ad-hoc `os.environ` reads outside the loader.
- **Alternatives considered:** Scattered env reads (rejected — untraceable, unvalidated); runtime config mutation (rejected — non-deterministic runs).

### ADR-009 — Resumable Pipeline via Persisted Checkpoints
- **Status:** Accepted
- **Date:** 2026-07-18
- **Context:** Generation is long-running and failure-prone (rate limits, transient errors). Restarting from the idea on every failure is unacceptable.
- **Decision:** The workflow is an explicit state machine; each stage persists a `StageStatus` transactionally. Re-runs skip `COMPLETED` stages and resume from the first incomplete/`FAILED` one. `--force <stage>` re-runs a stage deliberately.
- **Consequences:** Robust, cost-efficient runs; the DB is the source of truth for progress; stages must be idempotent.
- **Alternatives considered:** In-memory only (rejected — lost on crash); external workflow engine (rejected — premature dependency for MVP).

### ADR-010 — Structured, Correlated Logging (No `print`)
- **Status:** Accepted
- **Date:** 2026-07-18
- **Context:** Debugging an async, multi-stage, multi-scene pipeline requires traceable logs; user output and operator logs are different concerns.
- **Decision:** Structured logging (JSON in prod, readable in dev) with `contextvars` correlation (`run_id`, `project_id`, `stage`, `scene_id`), secret redaction, and per-stage timing. `print` is forbidden except in the presenter layer's deliberate user output.
- **Consequences:** Observability-ready without refactoring; clean separation of channels.
- **Alternatives considered:** Plain `print`/basic logging (rejected — untraceable in async fan-out).

### ADR-011 — `src/` Layout & Foundation Tooling Choices
- **Status:** Accepted
- **Date:** 2026-07-18
- **Context:** Sprint 001 (Project Foundation) had to place the approved Clean Architecture layers on disk and pick concrete foundation tools. The Architecture Document §4 illustrates the package tree without committing to a `src/` prefix, and names layers but not specific CLI/config/logging libraries.
- **Decision:**
  1. Adopt a **`src/` layout**: the package is `src/ai_video_factory/`. The approved Clean Architecture **layers are preserved unchanged** (`domain`, `application`, `infrastructure`, `interface`, `shared`); only the physical location gains a `src/` prefix. The cross-cutting `AppError` root lives in `src/ai_video_factory/errors.py` (imports stdlib only, so it never violates the inward dependency rule).
  2. **CLI:** Typer. **Config:** pydantic-settings. **Console/logging output:** Rich (console handler + `RichHandler`).
  3. **Formatter:** Ruff for both lint and format; **Black is not adopted** (confirming conventions §13). Running two formatters is avoided.
  4. **Packaging:** hatchling build backend; `factory` console script entry point.
- **Consequences:** Import hygiene improves (tests import the installed/`pythonpath` package, not accidental local modules). No change to the layer architecture, ADR-006, or dependency direction. `08_ENVIRONMENT.md` directory layout updated to show `src/`. Concrete tools remain replaceable behind the same layer boundaries.
- **Alternatives considered:** Flat `src/aivideo/` technical-type packages as first proposed in the Sprint 001 spec (rejected — would replace the approved layer architecture, contradicting §4 and ADR-006); root (non-`src`) layout (rejected — weaker import isolation); Black + Ruff (rejected — redundant formatters).

### ADR-012 — LLM Provider Abstraction (Protocol, Retry, Factory)
- **Status:** Accepted
- **Date:** 2026-07-18
- **Context:** The system must talk to many interchangeable LLM vendors (Gemini, Claude, OpenAI, OpenRouter, Ollama, DeepSeek, Qwen) without the application ever knowing which. This is the concrete realization of ADR-005 for text generation, one layer below the domain capability ports (`StoryGenerator`, `SceneBuilder`).
- **Decision:**
  1. Define a vendor-neutral `LLMProvider` **Protocol** (`generate`, `health_check`, `count_tokens`, `models`) in `infrastructure/providers/base/`, with strongly typed `LLMRequest`/`LLMResponse`/`TokenUsage`/`ProviderHealth` models. This LLM abstraction lives in **infrastructure**, not the domain — it is an internal detail the future domain adapters consume; the domain stays pure and the application never names a provider.
  2. Provider errors form `AIProviderError → {AuthenticationError, RateLimitError, TimeoutError, ProviderUnavailableError, InvalidResponseError}`, extending the existing `AppError → InfrastructureError → ProviderError` tree — one root, no parallel hierarchy. Concrete clients translate SDK exceptions at the boundary.
  3. Cross-cutting resilience is a shared `RetryPolicy` (exponential backoff; retries only 429/503/timeout) plus a configurable per-request timeout (`asyncio.wait_for`), applied by the provider — not duplicated per vendor.
  4. Each concrete provider isolates its vendor SDK behind a small typed client seam (e.g. `GeminiClient`), lazily importing the SDK, so the provider and its tests never depend on the SDK and unit tests make no real API calls.
  5. `ProviderFactory.create(settings)` selects the provider from config (`provider` driver); adding a vendor registers one builder, changing no existing code (OCP).
- **Consequences:** LLM vendors are swappable via configuration; the domain/application remain provider-agnostic; resilience and error translation are centralized. Consistent with ADR-005/§12 — a realization, not a deviation.
- **Alternatives considered:** A monolithic `AIProvider` interface spanning all media (rejected — ISP); putting the LLM port in the domain (rejected — it is an infrastructure detail, not a domain capability; the domain ports are `StoryGenerator`/`SceneBuilder`); depending on each vendor SDK directly in the provider (rejected — untestable, non-isolated).

### ADR-013 — Prompt Engine (configurable prompt root, Jinja2, service façade)
- **Status:** Accepted
- **Date:** 2026-07-19
- **Context:** The system needs a production-ready way to store, validate, and render prompt templates with variables, without any prompt text living in Python code. `06_PROMPT_RULES.md` originally suggested templates live beside each provider adapter (`infrastructure/providers/<stage>/prompts/`); Sprint 003 instead uses a single, configurable top-level prompt root.
- **Decision:**
  1. Prompt templates live under a **configurable prompt root** (`PromptSettings.root`, default `prompts/`, env `AIVF_PROMPTS__ROOT`), organized by stage (`prompts/story/*.md`, `prompts/image/*.md`). A prompt name is a `/`-separated path without extension (e.g. `story/idea`).
  2. The **engine is infrastructure** (`infrastructure/prompts/`): `PromptLoader` (read + cache + `PromptNotFoundError`), `PromptRenderer` (Jinja2, `StrictUndefined`), `PromptValidator` (exists + syntax + required variables), and a `PromptService` façade (`render`, `validate`, `list_prompts`). Errors extend `InfrastructureError` (`PromptError → PromptNotFoundError/PromptValidationError/PromptRenderError`).
  3. **No prompt text in Python** — all prompt content is in template files; code only loads/renders them.
  4. Rendering uses `StrictUndefined` so a missing variable is an explicit `PromptRenderError`; template syntax errors are `PromptValidationError`.
- **Consequences:** Prompts are editable and versionable as content, decoupled from code, and reusable by any future stage adapter via `PromptService`. Supersedes the location guidance in `06_PROMPT_RULES.md` §1 (the root is configurable, so per-adapter layouts remain possible by pointing the root there). CLI raw text is written as UTF-8 bytes to support international prompt content on legacy Windows consoles.
- **Alternatives considered:** Prompts beside each adapter (deferred — a single configurable root is simpler and centralizes tooling); a custom `str.format` templating (rejected — Jinja2 gives loops/conditionals, strict-undefined, and variable introspection); embedding prompts as Python constants (rejected — violates "no hardcoded prompt").

### ADR-014 — Story Idea Generator (infrastructure service, JSON mode, retry-once)
- **Status:** Accepted
- **Date:** 2026-07-19
- **Context:** Sprint 004 needs to generate structured story ideas from a brief (topic/style/platform/language) using the configured AI provider and the prompt engine, returning typed data.
- **Decision:**
  1. `StoryIdea` and `IdeaBrief` are **domain value objects** (`domain/value_objects/idea.py`) — pure, frozen, first real domain content.
  2. `IdeaGenerator` is an **infrastructure service** (`infrastructure/story/`) — it consumes `PromptService` and an `LLMProvider` obtained from `ProviderFactory`, exactly the "adapter that uses the LLM provider" role ADR-012 describes. It never calls a vendor SDK directly. No application use case / domain port is introduced (per CLAUDE.md — not ahead of its sprint).
  3. Output is requested in **JSON mode** (`LLMRequest.json_mode=True`), parsed and validated into `list[StoryIdea]`; on a parse failure the generation is **retried once**, then raises `IdeaParseError`.
  4. The prompt lives only in `prompts/story/idea.md` (no hardcoded prompt); it evolved from a single-prose idea to a multi-idea JSON template with variables `topic, style, target_platform, language, count`.
  5. Delivery: `ai-video-factory idea` prints a Rich table and saves `output/ideas.json` (UTF-8, `ensure_ascii=False`); international table output is emitted as UTF-8 bytes to avoid the legacy-Windows console crash.
- **Consequences:** Idea generation is provider-agnostic and testable with a fake `LLMProvider` (no real API). Evolving `idea.md` updated two Sprint 003 tests that pinned its old variable set. When a formal Story use case + domain port arrive, this service becomes the adapter behind it.
- **Alternatives considered:** Putting `IdeaGenerator` in `application` (rejected — it depends on the infrastructure LLM provider/prompt engine, which application must not import; ADR-012 places the LLM abstraction in infrastructure); free-text parsing instead of JSON mode (rejected — brittle); building prompt text in Python (rejected — violates "no hardcoded prompt").

### ADR-015 — Story Outline Generator (mirrors the idea generator)
- **Status:** Accepted
- **Date:** 2026-07-19
- **Context:** Sprint 005 expands one selected story idea into a full structured outline (metadata + N chapters), following the pattern set by the idea generator (ADR-014).
- **Decision:**
  1. `StoryOutline` and `ChapterOutline` are **domain value objects** (`domain/value_objects/outline.py`) — pure, frozen, non-empty-validated.
  2. `OutlineGenerator` is an **infrastructure service** (`infrastructure/story/outline_generator.py`) using `PromptService` + an `LLMProvider` from `ProviderFactory` — never a vendor SDK directly. `generate(idea, *, target_duration, chapter_count, language)` renders `prompts/story/outline.md`, requests **JSON mode**, parses/validates, and **retries once** on failure.
  3. Validation (`parse_outline`) enforces required fields + non-empty values (via the model) and that the **chapter count matches** the request; failures raise `OutlineParseError`.
  4. `read_idea(path, index)` selects a `StoryIdea` from a saved ideas JSON (the `idea` command's output); delivery is `ai-video-factory outline`, printing the outline and saving `output/story_outline.json`.
  5. The two presenters' UTF-8-safe emit was extracted into `interface/presenters/console_io.emit_renderable` (removes duplication; no behavior change).
  6. `prompts/story/outline.md` rewritten into a JSON `StoryOutline` template (vars: idea_title, idea_hook, idea_summary, target_duration, chapter_count, language).
- **Consequences:** Same testability as the idea generator (fake `LLMProvider`, no real API). No application use case / domain port introduced (per CLAUDE.md). Establishes the reusable template for later stage generators.
- **Alternatives considered:** Placing `OutlineGenerator` in `application` (rejected — same reasoning as ADR-014/ADR-012); an input `OutlineBrief` value object (rejected — the spec lists only `StoryOutline`/`ChapterOutline` as models; inputs are passed as arguments to avoid an unneeded abstraction).

### ADR-016 — Chapter Generator (full-story prose, computed duration)
- **Status:** Accepted
- **Date:** 2026-07-19
- **Context:** Sprint 006 turns a `StoryOutline` into narratable prose. The spec gives a single `StoryChapter` output and a CLI that takes only `--outline` (no chapter selector), so "the full story chapter" was interpreted as **the complete story rendered as one narration script** derived from the whole outline — the only reading consistent with one input and one output.
- **Decision:**
  1. `StoryChapter` is a **domain value object** (`domain/value_objects/chapter.py`): `title`, `content`, `estimated_duration_seconds` (`gt=0`).
  2. `ChapterGenerator` is an **infrastructure service** (mirrors ADR-014/015): renders `prompts/story/chapter.md` from the outline fields, requests **JSON mode**, parses, and **retries once** → `ChapterParseError`.
  3. The model returns only `{title, content}`; **`estimated_duration_seconds` is computed deterministically** from the content (`words × 60 / words_per_minute`, default 150 wpm) rather than trusting the LLM — reliable and test-deterministic.
  4. `read_outline(path)` loads the saved outline; delivery is `ai-video-factory chapter --outline <path> [--language]`, printing the chapter and saving `output/chapter.json`.
- **Consequences:** Completes the file-based chain `idea → outline → chapter`. Duration is stable regardless of provider. If the Lead intended per-chapter generation, add a `--chapter/--index` selector in a follow-up; the current service and prompt would extend cleanly.
- **Alternatives considered:** Trusting the LLM's `estimated_duration_seconds` (rejected — unreliable, non-deterministic tests); generating only chapter 1 or requiring a selector (deferred — not supported by the given single-arg CLI; whole-story reading fits the spec as written); placing the estimator in `domain/services` (kept in the parser for cohesion; revisit if reused).

### ADR-017 — Image Prompt Generator (prompt text only; injected style/aspect)
- **Status:** Accepted
- **Date:** 2026-07-19
- **Context:** Sprint 007 turns a `StoryChapter` into a list of cinematic image *prompts* (text) for a later image stage. No images are generated here.
- **Decision:**
  1. `ImagePrompt` is a **domain value object** (`domain/value_objects/image_prompt.py`): `scene_number`, `prompt`, `negative_prompt`, `aspect_ratio`, `style`, `camera`, `lighting`, `character_reference`, `environment`, `seed` (optional). Only `scene_number`/`prompt` (plus injected `aspect_ratio`/`style`) are required; descriptor fields default to `""`.
  2. `ImagePromptGenerator` is an **infrastructure service** (mirrors ADR-014/015/016): renders `prompts/image/image_prompt.md`, requests **JSON mode**, parses, and **retries once** → `ImagePromptParseError`.
  3. **`style` and `aspect_ratio` are project-level constants injected by the parser** onto every prompt (from CLI/defaults), overriding anything the model returns — guaranteeing consistency across visuals. The LLM supplies only creative fields.
  4. The visual count is a **hint** (`--count`, default 6) passed to the prompt; the parser accepts a non-empty list rather than enforcing an exact count (kept lenient to avoid brittle retries).
  5. `read_chapter(path)` loads the saved chapter; delivery is `ai-video-factory image-prompt --chapter <path> [--style --aspect-ratio --count --language]`, printing a table and saving `output/image_prompts.json`.
- **Consequences:** Completes the chain `idea → outline → chapter → image-prompt` (text only). Consistent `style`/`aspect_ratio` regardless of the LLM. This is *not* scene splitting — a single generation call produces numbered image prompts; no separate scene stage is introduced.
- **Alternatives considered:** Trusting the LLM's `style`/`aspect_ratio` per item (rejected — inconsistent); enforcing exact `count` like the outline's chapter count (deferred — image count is naturally variable, strictness adds failures); a separate scene-splitter stage feeding this (out of scope — forbidden this sprint).

### ADR-018 — Image Provider Layer (mirrors the LLM provider layer; reuses shared parts)
- **Status:** Accepted
- **Date:** 2026-07-19
- **Context:** Sprint 008 needs a swappable image-generation abstraction (starting with Gemini Imagen), parallel to the LLM provider layer (ADR-012) but for images.
- **Decision:**
  1. `ImageProvider` **Protocol** (`generate`, `health_check`, `models`) in `infrastructure/providers/image/base/`, with `ImageGenerationRequest`/`ImageGenerationResponse` models. Lives in **infrastructure** (like the LLM abstraction — ADR-012), never the domain.
  2. **Reuses the shared provider building blocks** — the `AIProviderError` hierarchy, `RetryPolicy`, `ProviderHealth`, `HealthStatus`, and the google-genai `map_status_to_error` — rather than duplicating them (image errors are provider-generic, not LLM-specific).
  3. `GeminiImagenProvider` (google-genai Imagen) isolates the SDK behind an `ImagenClient` seam (lazily imported); it saves the image via an injected `ImageStorage` and returns the saved path in the response. Retries transient errors once; timeout via `asyncio.wait_for`.
  4. `ImageStorage` (`infrastructure/media/`) writes sequentially numbered PNGs (`image_001.png`, ...). The provider owns saving so `ImageGenerationResponse.image_path` is meaningful.
  5. `ImageProviderFactory.create(settings, storage)` selects the provider from config; if the image API key is unset it reuses the LLM provider's key (both use the Gemini API).
  6. `ImageProviderSettings` config section (`provider`, `api_key`, `model`, `timeout`, `retry_count`). Delivery: `ai-video-factory image --input <image_prompts.json>` generates every image with a Rich progress bar and saves to `output/images/`.
- **Consequences:** Image generation is provider-agnostic and testable with a fake `ImagenClient`/`ImageProvider` (no real API). Completes the chain up to images. No video/ffmpeg/subtitle/TTS/workflow introduced.
- **Alternatives considered:** A single provider abstraction for both text and images (rejected — ISP; different request/response shapes); the provider returning raw bytes for the caller to save (rejected — `ImageGenerationResponse.image_path` implies the provider saves; injecting `ImageStorage` keeps it testable); a separate image API key with no fallback (rejected — needlessly forces configuring the same Gemini key twice).

### ADR-019 — Pipeline Runner (Phase 1: idea → outline → chapter → image prompts)
- **Status:** Accepted
- **Date:** 2026-07-19
- **Context:** Sprint 009 connects the existing generators into one orchestrated run, without redesigning anything or duplicating business logic.
- **Decision:**
  1. `PipelineRunner` (`infrastructure/pipeline/`) composes the four existing generators (`IdeaGenerator`, `OutlineGenerator`, `ChapterGenerator`, `ImagePromptGenerator`). It holds **no business logic** — only sequencing, persistence, and progress reporting.
  2. Placed in **infrastructure** (not `application/workflow`) because it composes infrastructure generators; an application use case may not import infrastructure. This follows the established pattern (ADR-012/014) and is a realization of the Architecture Document's `RunPipeline`, not a redesign.
  3. Stages run **sequentially**; each output is **persisted immediately** (`ideas.json`, `story_outline.json`, `chapter.json`, `image_prompts.json`) before the next stage. Any stage failure propagates and **stops the run**, leaving earlier outputs saved.
  4. `from_settings` builds **one** provider + prompt service and injects them into all four generators (no per-stage duplication).
  5. Progress is reported via an injected `on_stage(number, total, name)` callback, so the runner stays free of Rich; the `generate` CLI renders a Rich progress bar (`[1/4] Generate ideas`, …).
  6. Typed `PipelineRequest` / `PipelineResult`; delivery is `ai-video-factory generate --topic --style --platform [--chapters]`. It uses the first generated idea to continue. **No image generation, TTS, subtitle, ffmpeg, or upload.**
- **Consequences:** The end-to-end story chain is now one command. Testable with a single stage-aware fake provider (keyed on `request.metadata["stage"]`). Later phases (image generation, then media) extend by appending stages.
- **Alternatives considered:** Putting the runner in `application` (rejected — would import infrastructure generators, violating the inward rule; the generators are already infrastructure per ADR-014); the CLI orchestrating directly (rejected — keeps orchestration out of the thin delivery layer and untestable without the CLI); introducing generator Protocols now to host the runner in application (rejected — a redesign the sprint forbids).

---

### Index

| ADR | Title | Status |
|---|---|---|
| 001 | CLI First (No Web UI) | Accepted |
| 002 | Python 3.13, Async-First | Accepted |
| 003 | SQLite for Persistence | Accepted |
| 004 | No FastAPI for MVP | Accepted |
| 005 | Replaceable AI Providers | Accepted |
| 006 | Clean Architecture, enforced deps | Accepted |
| 007 | Pydantic v2 / Entity≠ORM | Accepted |
| 008 | Config-driven, fail-fast | Accepted |
| 009 | Resumable checkpoints | Accepted |
| 010 | Structured logging | Accepted |
| 011 | src layout + foundation tooling | Accepted |
| 012 | LLM provider abstraction | Accepted |
| 013 | Prompt engine (Jinja2, config root) | Accepted |
| 014 | Story idea generator | Accepted |
| 015 | Story outline generator | Accepted |
| 016 | Chapter generator | Accepted |
| 017 | Image prompt generator | Accepted |
| 018 | Image provider layer | Accepted |
| 019 | Pipeline runner (Phase 1) | Accepted |
