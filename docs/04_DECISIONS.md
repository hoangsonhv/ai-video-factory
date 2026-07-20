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

### ADR-020 — Speech (TTS) Provider Layer (mirrors the image layer; WAV under `.mp3`)
- **Status:** Accepted
- **Date:** 2026-07-19
- **Context:** Sprint 010 adds Vietnamese narration synthesis from `chapter.json`, parallel to the image provider layer (ADR-018) but for audio.
- **Decision:**
  1. `SpeechProvider` **Protocol** (`synthesize`, `health_check`, `list_voices`) in `infrastructure/providers/speech/base/`, with `SpeechSynthesisRequest` / `SpeechSynthesisResponse` and an internal `SynthesizedAudio`. Lives in **infrastructure** (like the other provider layers).
  2. **Reuses** the shared `AIProviderError` hierarchy, `RetryPolicy`, `ProviderHealth`, `HealthStatus`, and google-genai `map_status_to_error` — no duplication.
  3. `GeminiSpeechProvider` (google-genai TTS) isolates the SDK behind a `GeminiTtsClient` seam (lazily imported); it saves the audio via an injected `AudioStorage` and returns the path, duration, and sample rate. Retries transient errors once; timeout via `asyncio.wait_for`.
  4. **Format:** Gemini TTS returns raw PCM (16-bit mono, 24 kHz). MP3 transcoding requires ffmpeg, which is out of scope, so the PCM is wrapped into a valid **WAV** container (pure-Python `wave`) and saved under the spec's `output/audio/narration.mp3` path; `metadata.json` records the true `sample_rate`. A future media/transcode stage can produce real MP3.
  5. `SpeechProviderFactory.create(settings, storage)` selects the provider from config; if the speech API key is unset it reuses the LLM key. `SpeechProviderSettings` (`provider`, `api_key`, `model`, `voice`, `timeout`, `retry_count`). Delivery: `ai-video-factory tts --chapter <chapter.json>` with a Rich spinner; saves `output/audio/narration.mp3` + `output/audio/metadata.json` (duration, voice, provider, sample_rate).
- **Consequences:** Narration synthesis is provider-agnostic and testable with a fake `GeminiTtsClient`/`SpeechProvider` (no real API). Reuses `read_chapter`. No image/subtitle/ffmpeg/workflow changes.
- **Alternatives considered:** Bundling an MP3 encoder like `lameenc` (rejected — heavy native dependency for one stage; WAV suffices until a media stage exists); a single provider abstraction for image + speech (rejected — ISP, different request/response shapes); the provider returning raw bytes for the caller to save (rejected — `audio_path` in the response implies the provider saves; injecting `AudioStorage` keeps it testable).

### ADR-021 — Asset Pipeline Foundation (unifying layer that wraps existing providers)
- **Status:** Accepted
- **Date:** 2026-07-19
- **Context:** The Lead requested an "asset pipeline foundation" — a uniform `AssetResult`, generator interfaces (image/speech/subtitle/video), and an `AssetPipelineRunner`. This overlapped the existing `ImageProvider`/`SpeechProvider` (Sprint 008/010) and `PipelineRunner` (Sprint 009), and its literal "interfaces only, no implementation" collided with CLAUDE.md's no-placeholder / every-sprint-passes rules. The Lead chose to **wrap the existing providers (real, no placeholder)** and to **number this Sprint 011** (Sprint 010 was already the delivered Voice Generator).
- **Decision:**
  1. `infrastructure/asset_pipeline/`: a uniform `AssetResult` (`success`, `path`, `duration`, `metadata`), four generator **Protocols** (`ImageGenerator`, `SpeechGenerator`, `SubtitleGenerator`, `VideoComposer`), and `AssetPipelineRunner` (`generate_images`, `generate_voice`, `generate_subtitles`, `compose_video`).
  2. **Image and voice are real**: `ImageAssetGenerator`/`SpeechAssetGenerator` **delegate to the existing `ImageProvider`/`SpeechProvider`** — no business logic is duplicated (the providers still own generation/retry/save). This is the media-phase orchestrator, complementary to the story-phase `PipelineRunner`.
  3. **Subtitle and video are contracts only** (Protocols); the runner's `generate_subtitles`/`compose_video` raise a clear `AssetStageUnavailableError` until their sprints wire adapters in — a real guard, not dead code.
  4. CLI `ai-video-factory assets` shows a status table (images/voice ready; subtitles/video pending); it does **not** run generation. No actual TTS/image/subtitle/ffmpeg/video work in this sprint.
- **Consequences:** A single asset abstraction now spans all four media stages, reusing the provider layers. Deviates from the spec's literal "no implementation" so that CLAUDE.md's no-placeholder rule holds (image/voice adapters work). Future subtitle/video sprints add adapters and inject them into the runner — no changes to existing stages.
- **Alternatives considered:** Pure interface-only scaffolding (rejected by the Lead — violates no-placeholder/no-dead-code); making the generators replace the existing providers (rejected — a redesign and duplication); leaving `AssetResult` out and reusing the providers' typed responses directly (rejected — the Lead wants a uniform asset result across the four media stages).

---

### ADR-022 — Pollinations as the default (free, key-less) image provider for the MVP
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** The Gemini image provider (ADR-018) requires an API key and, on the free tier, returns HTTP 429 with a `limit: 0` image-generation quota — so the MVP cannot produce images out of the box. The Lead requested a free image provider ("Sprint 013 — Pollinations Image Provider"), selectable by configuration, without changing the `ImageProvider` interface or other providers. (Numbering collides with the earlier tts-hardening also labelled Sprint 013; the Lead's label is kept.)
- **Decision:**
  1. New `PollinationsImageProvider` (`providers/image/pollinations/`) implementing the existing `ImageProvider` protocol — with a `PollinationsClient` seam and an httpx-backed `RealPollinationsClient` (the only module doing HTTP). No API key is needed, so a live client is always built (no WARN-no-key path).
  2. Registered under the `pollinations` **driver** in `ImageProviderFactory` (ADR-005); Gemini Imagen remains available via `provider=gemini_imagen`. **No other provider was modified and no public API changed.**
  3. **Default flipped to `pollinations`** (model `flux`) in `ImageProviderSettings` and `.env.example`, so the MVP generates images for free with no key. Retry (×3) and serialised requests reuse the shared `ImageRateLimiter`; aspect ratio maps to width/height (longer side → 1024).
  4. The existing `image` command is unchanged — reads `output/image_prompts.json`, saves `001.png`…, writes the manifest, skips existing unless `--force`.
- **Consequences:** Image generation works out of the box with no credentials (verified live: 6 images generated). Pollinations returns JPEG bytes saved under `.png` (acceptable for MVP). Quality/latency are provider-dependent; Gemini stays a config switch away for higher fidelity.
- **Alternatives considered:** Keep Gemini default and only add Pollinations as an option (rejected — the goal is a working free MVP by default); add a new "free image" abstraction (rejected — the `ImageProvider` port already suffices per ADR-005).

---

### ADR-023 — Transcription Provider Layer for Subtitle Generation
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** Sprint 016 ("Subtitle Generation") needs a synchronized `.srt` from the narration audio + chapter text, with retry-on-failure and Vietnamese support. Producing timing that matches the audio requires a speech-to-text (transcription) provider — a capability not yet in the system. The Lead asked to "reuse the existing provider architecture" (ports & drivers, ADR-005).
- **Decision:**
  1. New `infrastructure/providers/transcription/` layer mirroring the speech/image layers: a `TranscriptionProvider` **Protocol** (`transcribe`, `health_check`) with vendor-neutral models (`TranscriptionRequest`, `TranscriptionSegment`, `TranscriptionResult`), a `GeminiTranscriptionProvider` behind a `GeminiTranscriptionClient` seam (lazy SDK import; sends the audio inline to a multimodal model and parses a JSON list of timed segments), a `TranscriptionProviderFactory` selecting by config `driver` (`gemini_transcription`), and `TranscriptionProviderSettings` (api-key falls back to the LLM key). Retry ×3 via the shared `RetryPolicy`; errors translated via `map_status_to_error`.
  2. Timing comes from the transcription (ASR) timestamps — best-effort alignment to the audio; the chapter text is passed as a **reference transcript** so the model fixes ASR wording errors.
  3. A pure `to_srt()` formatter (`base/srt.py`) renders segments as SubRip (`HH:MM:SS,mmm`, renumbered); `SubtitleStorage` (`media/`) writes the `.srt` as UTF-8 (Vietnamese-safe). The provider returns data; the CLI writes the file (separation of concerns).
  4. CLI `ai-video-factory subtitle --audio … --chapter …` (default `--language vi`, `--force`, skip-if-exists, progress + `_ensure_utf8_stdout` for legacy Windows). Default model `gemini-flash-latest` (a stable audio-capable alias; `gemini-2.5-flash` returns 404 "not available to new users" on this account).
- **Consequences:** Subtitles are generated by config-selected transcription providers with no core changes; the domain and other providers are untouched. Timing accuracy is provider-dependent (Gemini timestamps drift somewhat). The asset pipeline's `SubtitleGenerator` contract (ADR-021) stays a future integration point — not wired in this sprint.
- **Alternatives considered:** Heuristic timing (split chapter text over the audio duration) — rejected: no real audio alignment and the Lead specified a transcription provider. A dedicated ASR library (e.g. whisper) — rejected for the MVP: heavier dependency; the existing Gemini seam suffices via ports & drivers.

---

### ADR-024 — FFmpeg Video Composer (`compose`)
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** Sprint 017 composes the final portrait MP4 from existing assets (images + narration + subtitles) using ffmpeg only. ffmpeg is a blocking external tool that may be absent on a dev machine. The architecture already names a `VideoComposer` port (asset pipeline) and a `MediaError` for ffmpeg failures; blocking work must run off the event loop (ADR-002).
- **Decision:**
  1. New self-contained `infrastructure/video/` package: a **pure** `build_ffmpeg_command()` (argv generator — unit-testable without ffmpeg), a `parse_srt_cues()` timing reader, and `FfmpegVideoComposer` which **satisfies the existing `VideoComposer` protocol** (`compose_video(images, voice, subtitles) -> AssetResult`). No new port, no factory (single backend — avoids a placeholder abstraction).
  2. Composition: one image per subtitle cue (reusing the **last** image when images < cues); per-image Ken Burns `zoompan`; `xfade` crossfades between images (cumulative offsets); burned-in subtitles via the `subtitles` filter (Windows-escaped path); narration audio; H.264/AAC, 1080x1920, 30 fps, `-shortest`. Encoding params come from `VideoSettings`.
  3. The ffmpeg subprocess runs **off the event loop** (`asyncio.to_thread`) behind an injectable runner (mocked in tests); **retry once** on a non-zero exit, then `MediaError` with stderr. A missing binary → `FileNotFoundError` → `MediaError`.
  4. The `compose` CLI **verifies ffmpeg up front with the existing `check_ffmpeg()` diagnostics** and, if absent, exits with a clear "install FFmpeg" message. It only reads assets (never regenerates images/audio/subtitles) and writes `output/video/final.mp4` + `metadata.json` (duration, fps, resolution, image_count, subtitle_count).
- **Consequences:** Video composition works via a config-driven ffmpeg wrapper with no core/domain changes; the asset pipeline's `VideoComposer` contract is honoured (a future pipeline sprint can inject this composer). Command generation is fully tested; the real pixel output requires ffmpeg installed (verified by the operator). Timing is approximate where crossfades overlap cue windows (small fades).
- **Alternatives considered:** A MoviePy/PyAV dependency — rejected: the sprint mandates ffmpeg-only and it is already the documented media adapter. Building the video inside the asset-pipeline adapters — rejected: keeps ffmpeg concerns cohesive in `video/` and avoids touching unrelated modules.

---

### ADR-025 — Character & Scene Bible (Movie Builder)
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** Sprint 018 adds persistent characters and structured scenes so downstream stages can keep a character's look consistent. It must be **additive** — the existing story/image/voice/subtitle/compose stages and all current commands keep working unchanged.
- **Decision:**
  1. New domain value objects in `domain/value_objects/movie.py` — `Movie`, `Character`, `Appearance`, `Location`, `Camera`, `Scene` — frozen Pydantic models matching the `output/movie.json` schema exactly. Camera is a nested VO; **action / emotion / dialogue are Scene string fields** per the authoritative schema (the spec's "Action" model maps to `Scene.action`, keeping the JSON contract).
  2. New infrastructure `MovieBuilder` (`infrastructure/story/movie_builder.py`) mirroring the existing generator pattern: renders `prompts/story/movie.md`, calls the configured `LLMProvider` in JSON mode, parses with `parse_movie` (`movie_parser.py`), and **retries once** on a parse failure. `movie_writer.write_movie_json` persists UTF-8 JSON.
  3. **Character fixing/dedup**: the prompt instructs the model to list each character once with a permanent appearance; `parse_movie` additionally **deduplicates by id keeping the first occurrence**, so an appearance can never be changed by a later mention. Project `style`/`genre`/`duration` are injected when omitted (duration defaults to the chapter's estimated seconds).
  4. New `movie` CLI (`movie --input output/chapter.json`) extends the pipeline (Topic → Idea → Outline → Chapter → **Movie Builder** → `movie.json`). It reuses `read_chapter` and writes only `output/movie.json`.
- **Consequences:** Stories now carry a reusable "movie bible" (persistent characters + cinematic scenes with camera/action/emotion/image_prompt/video_prompt). No existing generator, the image pipeline, TTS, or compose was modified. A `MovieBuildError` was added to the story error module. Verified live: schema-valid `movie.json` (4 deduped characters, 5 locations, 8 scenes) from the real chapter.
- **Alternatives considered:** Adding character extraction into the existing chapter/image-prompt generators — rejected: would modify shipped stages (forbidden this sprint) and couple concerns. A separate persistence store for characters — rejected for MVP: a single `movie.json` artifact is enough and matches the file-per-stage convention.

---

### ADR-026 — Character Consistency Engine (`character build` / `character inject`)
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** Sprint 019 must guarantee that a character looks the same in every scene. ADR-025 fixed each character's *appearance* inside `movie.json`, but each scene still carried its own free-form `image_prompt`/`video_prompt`, so the image backend received a fresh description per scene and drifted. The sprint forbids modifying the Movie Builder or the image provider — this must be a new stage only.
- **Decision:**
  1. New domain value objects in `domain/value_objects/character_library.py` — `CharacterLibrary`, `CharacterProfile`, `NormalizedAppearance`, `NormalizedOutfit` — frozen Pydantic models matching the `output/character_library.json` schema exactly (`id`, `master_prompt`, `negative_prompt`, `seed`, `reference_image`, `appearance`, `outfit`, `voice_profile`, `version`). `appearance` holds the permanent physical traits (hair/eyes/face/body) and `outfit` the wardrobe (clothes/accessories), so clothing changes can never be mistaken for identity changes.
  2. New `infrastructure/character/` package with `CharacterConsistencyService`, which is **deterministic and offline** — no AI provider, no network. Rebuilding from the same `movie.json` yields a byte-identical library, which is what makes runs reproducible. It: normalizes traits (collapse whitespace, strip trailing punctuation, lowercase — names and dialogue are never normalized); composes **one `master_prompt` per character** in a fixed trait order, ending in an explicit consistency clause; merges shared base negative terms with the character's own; and derives the `seed` from `SHA-256(character_id)` so the same id always produces the same seed.
  3. **Duplicate detection/merge**: records whose ids (or, lacking an id, names) normalize equal are collapsed into one profile. The **first occurrence wins** for every populated trait (consistent with ADR-025); a later record may only fill traits the first left empty and contribute negative terms. This is the second line of defence behind the builder's dedup.
  4. `CharacterPromptInjector` rewrites each scene prompt as `<master prompts> | <original prompt> | negative: <terms>` — master **prepended**, negative **appended**, the scene's own direction **preserved verbatim**. It is **idempotent** (re-injecting recovers and reuses the original prompt), and a scene referencing an id absent from the library raises `CharacterLibraryError` rather than silently emitting an undescribed character. Output is a full, schema-valid `Movie` (`movie_consistent.json`) so every downstream stage can consume it unchanged.
  5. New `character` CLI group: `character build --input output/movie.json` → `output/character_library.json`; `character inject --movie output/movie.json [--library ...]` → `output/movie_consistent.json`. Both read only; neither touches `movie.json`, images, TTS, or compose.
- **Consequences:** Scene prompts are now bound to a single canonical description plus a stable seed per character, which is the mechanism for cross-scene consistency. The pipeline gains an optional stage: Chapter → Movie → **Character build → Character inject** → image generation (which can be pointed at `movie_consistent.json` in a later sprint — wiring is deliberately **not** done here). A new `CharacterLibraryError` was added. Verified live on the real `movie.json`: 4 profiles with distinct deterministic seeds, 10/10 scenes injected, originals preserved, source file unmodified.
- **Alternatives considered:** Generating master prompts with the LLM — rejected: non-deterministic, so the same character could drift between runs, defeating the purpose; the movie bible already contains the structured traits needed. Mutating `movie.json` in place — rejected: destroys the original scene direction and would modify the Movie Builder's artifact (forbidden this sprint). Storing the library inside `movie.json` — rejected: the sprint mandates a separate `character_library.json`, and a separate file lets the library be edited or reused independently.

---

### ADR-027 — AI Video Provider Layer (abstraction only)
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** Sprint 020 prepares for AI video generation (scene → clip). The commercial landscape (Veo, Kling, Runway, Hailuo, …) is volatile, expensive, and not yet chosen, so the sprint mandates building **only the abstraction** — no commercial integration — while the existing slideshow compose pipeline keeps working untouched. Note that `infrastructure/video/` already existed (ADR-024, the ffmpeg composer), so this is a **subpackage**, not a new top-level package.
- **Decision:**
  1. New `infrastructure/video/providers/` subpackage, keeping every video concern under `infrastructure/video/` as the sprint specified. This deviates from the `infrastructure/providers/<capability>/` convention used by the LLM, image, speech and transcription layers; the sprint's explicit path won, and the deviation is recorded here rather than silently resolved either way.
  2. A `VideoProvider` **Protocol** (`generate`, `supported_models`, `health_check`, plus a `name`) — structural, matching the other provider layers, so a driver satisfies the contract without importing or inheriting from it (ADR-005). Vendor-neutral models: `VideoGenerationRequest` (scene_id, prompt, negative_prompt, duration, aspect_ratio, fps, seed, reference_images, camera, style, motion_level — `camera` reuses the domain `Camera` VO), `VideoGenerationResult` (scene_id, provider, model, status, remote_job_id, video_path, preview_path, duration, metadata) and a `VideoJobStatus` enum. `QUEUED`/`RUNNING` and `remote_job_id`/`preview_path` are unused by local providers and exist so an asynchronous remote driver needs no model change.
  3. `VideoProviderRegistry` maps a config `provider` string to a driver: `register` / `names` / `is_registered` / `create` / `create_default` / `health_check` (concurrent, reporting every driver and flagging the configured default). It is **constructed, never module-global** — `build_default_registry()` returns a fresh instance — so there is no global mutable state and tests register fakes in isolation.
  4. New `VideoProviderSettings` config section (`VIDEO_PROVIDER` family): `provider` / `model` / `timeout` / `retry_count`, read as `AIVF_VIDEO_PROVIDER__*` per the established nesting convention (ADR-008). It is a **separate section from `VideoSettings`** (`AIVF_VIDEO__*`, the ffmpeg composition settings) so the compose stage's configuration is untouched.
  5. `MockVideoProvider` (development only) renders each scene locally with the existing ffmpeg approach — same binary, resolution, fps and codecs from `VideoSettings` — writing `output/video_clips/scene_001.mp4`, `scene_002.mp4`, … from a reference image when one exists and a colour card otherwise. It reuses the composer's injectable `FfmpegRunner` seam (mocked in tests), honours `timeout` and `retry_count`, and translates every failure into `VideoProviderError`. Its `health_check` reports **WARN** (it is not AI video) and **FAIL** when ffmpeg is absent. A new pure `build_clip_command()` generates the argv, so `ffmpeg_command.py` and `FfmpegVideoComposer` were **not modified**.
  6. New `video` CLI group: `video providers` (list + configured default), `video doctor` (health per driver, non-zero on FAIL), `video generate --scene output/movie_consistent.json` (one clip per scene, continue-past-failure with a per-scene status table, non-zero exit if any scene failed).
- **Consequences:** The system can be built and tested against a video-generation contract while **no commercial provider is integrated**; adding one later means satisfying the protocol and registering a builder — no existing code changes. The slideshow pipeline is fully backward compatible: `compose`, `VideoSettings`, `FfmpegVideoComposer` and every existing command are unchanged. Verified against the real `movie_consistent.json`: 10 scenes → 10 requests (9:16 derived from 1080x1920, injected character prompts and camera carried through) → correct ffmpeg argv → `completed` result. A **real render remains unverified on this machine** — ffmpeg is still not installed (the same pre-existing blocker as ADR-024).
- **Alternatives considered:** Placing the layer at `infrastructure/providers/video/` for convention symmetry — rejected: the sprint named `infrastructure/video/`, and splitting video concerns across two trees is worse than one documented deviation. An ABC instead of a Protocol — rejected: every sibling provider layer uses a Protocol, and structural typing keeps drivers free of a base-class import. Making the mock return fabricated paths without rendering — rejected: real, playable clips let the downstream stages be developed honestly against the abstraction.

---

### ADR-028 — Kling AI Video Provider (first real video driver)
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** Sprint 021 integrates the first real AI video provider behind the Sprint 020 contract (ADR-027). Kling is **asynchronous** (submit → poll → download) and **paid**, unlike every provider integrated so far, and its API could not be exercised for real: no Kling credentials were available.
- **Decision:**
  1. New `infrastructure/video/providers/kling/` — `client.py` (the only module doing HTTP, behind a `KlingClient` protocol seam with an httpx-backed `RealKlingClient`), `models.py` (`KlingJob` + vendor→`VideoJobStatus` mapping), `provider.py` (`KlingVideoProvider`). Registered as the `kling` driver; **no existing code changed** beyond the registry entry, one settings section and the CLI.
  2. **Image-to-video only**, per the sprint: each scene's generated image plus its `video_prompt` become one clip. The job lifecycle is exposed as four separate methods (`submit_job`, `poll_job`, `download_result`, `cancel_job`) and composed by `generate()`, so each step is independently testable and reusable.
  3. **`mock` remains the default driver.** Kling requires a paid key, so flipping the default would break `video generate`/`video doctor` for anyone without credentials. Select Kling with `AIVF_VIDEO_PROVIDER__PROVIDER=kling`.
  4. Configuration reuses the existing `VideoProviderSettings` section rather than adding a Kling-specific one: `api_key` = `KLING_API_KEY`, `base_url` = `KLING_BASE_URL`, `model` = `KLING_MODEL`, plus `poll_interval` / `poll_timeout` (bounding one remote render, distinct from `timeout` which bounds one HTTP request) and `cost_per_second`.
  5. **Resilience:** transient failures (429/503/timeout) retry with exponential backoff via the shared `RetryPolicy`; terminal failures (auth, malformed response) do not. A job exceeding `poll_timeout` is **cancelled** rather than left running and billing. Every vendor and transport error is translated into `VideoProviderError`, so a provider outage produces a clean per-scene failure and a non-zero exit — never a crash. An unknown `task_status` is treated as *running*, so a vendor vocabulary change stalls a poll instead of discarding a live job.
  6. **Cost is an estimate, not a quote:** Kling returns no price, so the manifest's `cost` is `duration × cost_per_second` and reads `0.0` (meaning *unknown*) until an operator configures their rate.
  7. `video generate` gains `--movie` (with `--scene` kept as a working alias) and `--images`, writes `output/video_clips/manifest.json` (scene_id, provider, model, status, duration, cost, remote_job_id, filename + total_cost), and drives a phase progress bar (submitting → waiting → downloading → completed) via a provider callback. Scenes are matched to images by **position** (`001.png` → first scene).
  8. `video doctor` now fails **only on the configured provider**: an unconfigured alternative driver (Kling with no key while `mock` is selected) is reported for information without failing the command. This changed because a second driver made the old "any FAIL" rule wrong.
- **Consequences:** The project can generate real AI video once credentials are supplied, with no change to the compose, TTS or image stages. **The live Kling API is unverified** — the endpoint shapes follow Kling's published image-to-video documentation, every test uses an httpx `MockTransport`, and an end-to-end run was verified against a local stub HTTP server (submit → poll `processing`→`succeed` → download → manifest). Because `base_url`, model and credentials are all configuration, a vendor-side difference is a settings change or a localized `client.py` fix. Kling's cancellation endpoint is the least certain part (it is not clearly documented publicly) and is used only on a poll timeout, where failure is logged and swallowed.
- **Alternatives considered:** Making Kling the default driver — rejected: it would break the CLI for every user without a paid key. A Kling-specific settings section — rejected: the existing `VIDEO_PROVIDER` section already carries provider/model/key/timeout, and per-vendor sections would multiply with every driver. Fabricating a cost figure — rejected: reporting a made-up price is worse than reporting `0.0` and documenting it as unknown. Synchronous "submit-and-block" without exposing the lifecycle — rejected: the sprint asked for the four methods, and separating them makes the timeout/cancel path testable.

---

### ADR-029 — Cost Guard for Paid Video Generation
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** Sprint 021 made `video generate` able to spend real money — one paid Kling job per scene, ten scenes on the current movie, with no preview, no ceiling and no confirmation. A mistyped command or a stale default could bill an operator immediately.
- **Decision:**
  1. **`--dry-run`** prints the plan (provider, model, scene count, jobs, duration, estimated cost) and submits nothing. It deliberately **does not build the provider**, so a dry run works without credentials — the preview must never be the thing that fails.
  2. **`--limit N`** submits only the first N scenes (`min=1`, so `--limit 0` is rejected by the CLI rather than silently doing nothing). The plan reports the run as *limited* so a capped run is never mistaken for a full one.
  3. **Interactive confirmation** whenever `provider != mock` and `--yes` was not passed. The prompt **defaults to No**, and a non-interactive stream (CI, piped input, closed stdin) **declines** rather than spending money unattended. Declining is a deliberate user choice, so it exits **0**, not an error code.
  4. A single `GenerationPlan` (`video/providers/cost.py`) backs both the dry-run preview and the manifest's estimates, so the number shown before confirming is the number recorded afterwards.
  5. The manifest's ambiguous `cost` becomes **`estimated_cost`** (projected before the run) and **`actual_cost`** (what the finished job worked out to; `0.0` for a failed scene, since nothing was rendered), with `total_estimated_cost` / `total_actual_cost` replacing `total_cost`. Both remain `0.0` when no `cost_per_second` rate is configured — meaning *unknown*, never *free*.
- **Consequences:** Spending money now requires either an interactive "y" or an explicit `--yes`, and an operator can preview and cap any run first. The manifest distinguishes what was projected from what was incurred, which is what makes a run auditable after the fact. `mock` is unaffected — it spends nothing and never prompts. **Breaking change to `manifest.json`**: the `cost`/`total_cost` fields are replaced; the manifest is a regenerated artifact, so no migration is provided.
- **Alternatives considered:** A cost ceiling that aborts mid-run — rejected for now: it would need per-job cost reporting the provider does not give, and a partial run is harder to reason about than a capped one. Confirming per scene — rejected: ten prompts is worse than one. Keeping `cost` alongside the two new fields — rejected: three cost fields with overlapping meanings is exactly the ambiguity this removes.

---

### ADR-030 — AI Director (cinematic shot planning)
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** Sprint 022 replaces generic per-scene video prompts with real shot planning. The stage sits between the consistency pass and video generation (Movie → **Director** → Directed Movie) and must not disturb the Movie Builder, the Character Library, the providers, image generation or compose.
- **Decision:**
  1. New domain VOs in `domain/value_objects/director.py`: `DirectorNotes` (the sixteen specified fields), `DirectedScene(Scene)` and `DirectedMovie(Movie)`. They **subclass** the Movie Builder's models rather than adding fields to them, so `movie.py` is untouched and `movie_directed.json` still validates as a plain `Movie` — every existing stage can read it.
  2. The shot plan is **LLM-generated**, not derived. Fields like `hair_motion`, `cloth_motion` and `environment_motion` require reading the scene's content ("rides through neon traffic" → hair whipping back, jacket flapping, signs blurring past); a deterministic mapper could only emit filler, which is precisely the generic output this sprint exists to remove. One call plans the whole movie, mirroring the Movie Builder's pattern (prompt template, JSON mode, retry once).
  3. The **`director_prompt` composition is pure and deterministic** (`prompt_builder.py`). The creative judgement is the model's; assembling it is reproducible and fully unit-tested.
  4. **Honest fallback, no filler.** A field the model omits is filled from what the scene *already* states (its `camera`, `action`, `emotion`, and the movie `style`); anything no source can supply stays empty, and the prompt builder omits empty fields. A scene the model skips entirely still gets a plan derived from its own camera language.
  5. **Identity is not re-described.** The prompt template explicitly forbids describing faces, hair colour, clothing or build — that would contradict Sprint 019's consistency guarantee. Identity enters the prompt only via the character library's `master_prompt`, prepended by the builder.
  6. The prompt is **shaped for video, not stills**: leading identity, then shot and camera motion, then a motion breakdown (subject / hands / pose / expression), then secondary motion (hair / clothing / environment) that a still prompt never carries, then lighting, mood, setting, duration and transitions, closing with a temporal-coherence directive ("continuous single-take motion, temporally coherent, consistent character identity in every frame").
  7. New `director` CLI: `director --movie output/movie_consistent.json [--library …]` → `output/movie_directed.json`. The library is optional — without it the prompt carries camera and motion language only, and the command says so.
- **Consequences:** Scenes now carry a full shot plan plus a video-model prompt, while every original scene field (including `video_prompt`) is preserved verbatim — the director *adds*, never rewrites. `movie_directed.json` is a superset document, so no downstream stage needs changing to read it. Nothing consumes `director_prompt` yet; pointing the video stage at it is a later sprint's call. Verified live on the real 10-scene movie: all 16 fields populated, five distinct shot types, genuine secondary motion, source file unmodified.
- **Alternatives considered:** Adding `director`/`director_prompt` directly to `Scene` — rejected: it would alter the Movie Builder's schema and every test asserting it. A fully deterministic director — rejected: it cannot infer motion from scene content and would emit exactly the generic phrasing being replaced. Letting the director rewrite `video_prompt` in place — rejected: destroying the original makes the stage irreversible and unauditable.

---

### ADR-031 — Director Provider Resilience (per-scene retry, partial, resume)
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** Sprint 022's director planned the whole movie in **one** LLM call. A single transient Gemini failure therefore destroyed the entire run — ten scenes of work lost to one 503. Sprint 022A makes the stage survive a flaky provider.
- **Decision:**
  1. **One call per scene.** Independent per-scene retry is impossible with a bulk call, so the director now issues one request per scene. Each scene carries the previous scene's shot plan as context, preserving the cross-scene rhythm the bulk call gave for free.
  2. **Per-scene retry**: five retries with exponential backoff (1s, 2s, 4s, 8s, 16s) and **±20% jitter**, on 429/500/502/503/504 and connection/read timeouts. Terminal errors (auth, malformed response) are not retried. Jitter and a retry hook were added to the shared `RetryPolicy` as **opt-in** parameters (`jitter=0.0` default), so every other provider keeps its exact existing timing.
  3. **Transport errors are now translated.** The Gemini client caught only the SDK's `APIError` — which exists only once an HTTP response arrives. A connection timeout, read timeout or dropped socket escaped as a raw `httpx`/builtin exception: untranslated, unretried, and a violation of the "no raw vendor exceptions cross inward" rule. `map_transport_error()` now converts them to retryable `TimeoutError`/`ProviderUnavailableError` at all three SDK call sites. **This was the actual defect behind the reported failure**, not the 503 handling, which was already correct.
  4. **Failure is isolated.** A scene that exhausts its retries is left with empty `director`/`director_prompt` and the run continues. Emptiness is the resume marker — a failed scene is deliberately *not* given fallback notes, because that would make it indistinguishable from a successful one.
  5. **Partial output**: when some scenes succeeded, the result is written to `movie_directed.partial.json` and the command exits non-zero. A complete run writes `movie_directed.json` and deletes any stale partial. If *no* scene succeeded, nothing is written.
  6. **`--resume`** reads the partial (falling back to the complete file) and reuses every scene that already has a `director_prompt`, planning only the rest.
  7. A `DirectionReport` (directed / failed / retries / skipped / failed scene ids) is returned by `direct()` and rendered at the end of every run.
- **Consequences:** A flaky provider now costs individual scenes rather than whole runs, and `--resume` finishes the job without re-spending on completed work. **The cost of this is 10× the requests** for a ten-scene movie — noticeably more quota and wall-clock than the single bulk call, which matters on a rate-limited key. `direct()` now returns `(DirectedMovie, DirectionReport)`, a breaking change to Sprint 022's signature; the Sprint 022 tests were updated accordingly.
- **Alternatives considered:** Keeping the bulk call and retrying it whole — rejected: it cannot satisfy "continue directing scene 4 after scene 3 fails", and a retry re-spends the entire movie's tokens. Giving failed scenes derived fallback notes — rejected: it would produce a plausible-looking plan that `--resume` could never find. A separate director-only retry helper — rejected: duplicating backoff logic when the shared policy needed only an opt-in parameter.

---

### ADR-032 — Director plans the whole movie in one request (supersedes ADR-031 §1–2)
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** ADR-031 split director planning into one request **per scene** so a transient failure would cost one scene instead of the run. In practice the cure was worse than the disease: a ten-scene movie made ten requests, exhausting a rate-limited Gemini key far faster than the single bulk call it replaced, and multiplying token cost. The Lead rejected it.
- **Decision:**
  1. **One provider request plans the whole movie.** The prompt carries every scene, the **character library** (ids and voice notes only — never appearance, which would break ADR-026 consistency) and the **locations**; the model answers with a single `{"scenes": [...]}` block covering them all. Planning ten scenes costs one call.
  2. **Retries re-ask that one request, never per scene.** Transient transport failures (429/5xx, connection and read timeouts) back off exponentially with jitter inside the request; an **unparseable answer re-asks the whole question** up to `PARSE_ATTEMPTS` (3) times. This is what ADR-031's requirement 5 asked for and now applies at the right granularity.
  3. **Mapping**: each returned block is matched to its scene by `scene_id`. A scene the answer omits is left unplanned (empty `director_prompt`) rather than given filler, exactly as before — it is not chased with an extra call.
  4. **Retained from ADR-031** (they were never the problem): the Gemini transport-error translation (§3 — connection/read timeouts previously escaped untranslated), the opt-in `jitter`/`on_retry` on the shared `RetryPolicy`, partial output to `movie_directed.partial.json`, `--resume`, and the `DirectionReport`. `--resume` now re-asks only the unplanned scenes — still in **one** request.
- **Consequences:** Cost and rate-limit pressure return to Sprint 022 levels (one call per run) while keeping the resilience work. The loss is granularity: one unparseable answer now costs the whole movie rather than one scene, mitigated by re-asking up to three times and by `--resume`. `ADR-031 §1 (per-scene planning) and §2 (per-scene retry) are superseded`; the rest of ADR-031 stands.
- **Measured during verification (both remain open):**
  - **The `google-genai` SDK retries internally.** One `generate_content()` call produced ~4 HTTP POSTs against a failing endpoint, so our 6 logical attempts became 24 requests. Our retry layer multiplies with the SDK's rather than replacing it.
  - **`RetryPolicy` under-waits when the server asks for longer than `max_delay`.** Gemini replied "retry in 51s"; we retried in 16.5s because the hint is capped by `max_delay=16`, guaranteeing another 429. The hint should be honoured above the cap. Not changed here — it affects every provider and was outside this sprint's scope.
- **Alternatives considered:** Batching a few scenes per call — rejected: it reintroduces multi-call cost for a granularity benefit the Lead did not ask for. Keeping per-scene planning behind a flag — rejected: two planning paths to maintain and test for no stated need.

---

### ADR-033 — Batch Director + Shot Planner
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** Sprint 022's director produced one scene-level "shot plan" block per scene — sixteen adjectives describing how a whole 9-second scene was filmed. An AI video model renders a *shot*, not a scene, so that granularity was wrong: a single 9s prompt cannot express a cut. Sprint 023 replaces it with a per-scene **shot list**, keeping the single-request rule established in ADR-032.
- **Decision:**
  1. **New domain shape.** `DirectorNotes` (the sixteen scene-level fields) is **replaced** by `Shot` — the thirteen specified fields (`id`, `duration`, `camera`, `camera_motion`, `lens`, `framing`, `subject`, `action`, `expression`, `environment_motion`, `lighting`, `transition`, `video_prompt`). `DirectedScene` now carries `shots: tuple[Shot, ...]` instead of `director` + `director_prompt`. Keeping the old block would have left dead data nothing populates.
  2. **Still exactly one provider request** (ADR-032 stands): the prompt carries every scene, the cast and the locations, and the answer is one `{"scenes": [{"scene_id": n, "shots": [...]}]}` document. Retries re-ask that request; an unparseable answer re-asks up to three times. Never per scene.
  3. **The 3–8 shot and 2–5 second rules conflict for short scenes** — three shots of at least two seconds need a six-second scene. `target_shot_count()` resolves it by preferring the 3–8 band but never asking for more shots than the scene can physically hold: a 5s scene gets 2 shots, not 3. The prompt states the per-scene target; the parser enforces the bounds on whatever comes back.
  4. **Deterministic repair in the parser**: shot ids are **renumbered** 1..N per scene (ordering is ours, not the model's), durations are **clamped** into 2–5s with a missing value falling back to an even split of the scene, and more than eight shots are **trimmed**. Structural failures — no JSON, no scenes, no usable shots — are reported, never guessed at.
  5. **Each shot's `video_prompt` is composed deterministically** from the character library's master prompt, the shot's camera and motion fields, the setting, and the model's own one-line description folded in as the beat. Identity and negatives come from the library, never the model, so a shot can never contradict the character bible (ADR-026).
  6. **The scene's injected prompt is stripped before it is sent.** `movie_consistent.json` has each master prompt prepended to every scene prompt; passing that through restated the appearance the director is told not to describe. `_beat()` removes any library master prompt and the trailing negative tail, sending only the beat. *Found during verification — the cast section alone was not enough.*
- **Consequences:** A ten-scene movie now yields ~30 shots, each with its own render-ready prompt, at the cost of one LLM call. `movie_directed.json` changes shape (`director`/`director_prompt` → `shots`), which is breaking for anything reading Sprint 022 output — nothing does yet. Partial output, `--resume` (now keyed on "scene has shots") and the direction report are retained unchanged. Verified on the real 10-scene movie with a stubbed provider: 1 request, 30 shots, all durations in range, ids renumbered, identity present in every prompt and appearance absent from the request. **Not verified against the live API — the Gemini key is quota-exhausted.**
- **Alternatives considered:** Keeping `director` alongside `shots` — rejected: nothing would populate it. Letting the model's raw `video_prompt` stand as the final prompt — rejected: it would carry no character identity and break consistency. Enforcing 3–8 shots strictly — rejected: impossible for scenes under six seconds, and failing a scene over arithmetic the model cannot satisfy is worse than accepting two shots.

---

### ADR-034 - OpenRouter as the Director's LLM Provider
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** The director had been running on Gemini, whose free-tier quota was repeatedly exhausted mid-sprint (Sprints 022A-023 could never complete a live run). OpenRouter fronts many models behind one OpenAI-compatible endpoint, letting the director run on a model chosen for structured JSON without changing any calling code.
- **Decision:**
  1. New `infrastructure/providers/openrouter/` - `RealOpenRouterClient` (the only module doing HTTP, behind an `OpenRouterClient` seam) and `OpenRouterProvider`, which satisfies the **existing** `LLMProvider` protocol. No caller can tell it from the Gemini provider.
  2. **The director gets its own provider selection.** `ProviderFactory.create_director()` reads `AIVF_DIRECTOR_PROVIDER` and falls back to the general provider when unset; `ProviderFactory.director_model()` resolves the matching model. The story pipeline's own provider is untouched.
  3. **Configuration uses the flat names the operator was given** - `AIVF_DIRECTOR_PROVIDER`, `AIVF_OPENROUTER_API_KEY`, `AIVF_OPENROUTER_MODEL` - rather than this project's `AIVF_SECTION__FIELD` nesting. Those exact names were specified, so they win; `Settings.openrouter` re-exposes them to the code as one typed `OpenRouterSettings` object, keeping call sites tidy.
  4. Default model **`deepseek/deepseek-chat-v3`**; default director provider **`openrouter`**, so the requirement "the director must use OpenRouter instead of Gemini" holds out of the box. `AIVF_DIRECTOR_PROVIDER=gemini` switches back.
  5. `count_tokens()` **estimates** (~4 characters per token) because OpenRouter exposes no counting endpoint. Documented as an approximation rather than presented as exact.
- **Consequences:** The director no longer depends on the Gemini quota. No business logic changed - only which provider object the director is handed. 53 new tests, all HTTP mocked via `httpx.MockTransport`. **Unverified against the live OpenRouter API** - no credentials were available; the endpoint shapes follow OpenRouter's published OpenAI-compatible contract.
- **Alternatives considered:** Replacing Gemini globally - rejected: the sprint asked only for the director, and the story stages work. Nesting the config as `AIVF_OPENROUTER__API_KEY` for house consistency - rejected: the operator was handed specific names, and a third deviation flag helps nobody.

---

### ADR-035 - Storyboard Builder
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** The directed movie holds shots grouped under scenes, but nothing places them on a timeline or ties them to the narration. Rendering, subtitling and audio slicing all need absolute positions.
- **Decision:**
  1. New domain VOs in `domain/value_objects/storyboard.py` - `StoryboardShot` (the 20 specified fields), `AudioSegment` and `Storyboard`. A storyboard is the movie **flattened**: every shot of every scene in order, each with an absolute `speech_start`/`speech_end`, so a shot's position never depends on reading the ones before it.
  2. New `infrastructure/storyboard/` - `builder.py` (pure timeline + narration mapping), `narration.py` (its own `.srt` parser that keeps the **text**, which the compose stage's timing-only parser discards), `reader.py`, `errors.py`. **Deterministic and offline**: no provider is contacted, and compose is untouched.
  3. **Shot durations are never rewritten to chase the narration.** They come from the director and stay put; a shot stretched to fit speech would leave the permitted 2-5s band. Where the two lengths disagree the storyboard reports `drift` instead.
  4. **Narration is mapped by overlap**, not containment: a shot's `subtitle` is whatever the narrator is saying while it is on screen, and its `audio_segment` is the matching slice of the track, clipped to the track's real length.
  5. **`image_prompt` is composed as a still** - the same identity and framing as the video prompt, minus the motion, since it describes one frame. `video_prompt` is carried through from the director untouched.
  6. The CLI **warns when the subtitles are mistimed** - if the `.srt` span disagrees with the audio's real duration by more than 10%, every mapped subtitle is misplaced, which is worth saying rather than emitting a confidently wrong storyboard.
- **Consequences:** `output/storyboard.json` gives one addressable, timed shot list for the render stages to consume. Verified on the real movie: 30 shots over 10 scenes, 90.0s, contiguous timeline. That run also surfaced a **real data defect**: `narration.srt` is timed to 109.5s while the narration audio is 66.7s, so the existing subtitles are badly mistimed - the new warning catches exactly this.
- **Alternatives considered:** Stretching shots to fit the narration - rejected: it would violate the director's duration rules and silently distort the plan. Reusing the compose stage's `parse_srt_cues` - rejected: it deliberately drops subtitle text, and changing it was out of scope.

---

### ADR-036 - AI Video Generation from the Storyboard
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** Sprint 025 turns `storyboard.json` into AI video clips. Two requirements in the spec conflicted with the existing project and were resolved with the Lead before building: the spec's **1920x1080** against the project's portrait 1080x1920 pipeline, and the spec's **4-8s clips** against Sprint 023's 2-5s shot durations (the real storyboard is 30 shots of exactly 3s).
- **Decision:**
  1. **Portrait, from configuration.** Clips are rendered at `VideoSettings` (1080x1920, 9:16), so they match compose, which this sprint must not modify. The frame and rate travel on the request (`width`, `height`, `fps`), so landscape is an env change rather than a code change. *Lead's call: the 1920x1080 in the spec was a transposition slip.*
  2. **Shots are merged into clips, not stretched.** `clip_planner.plan_clips()` groups **consecutive shots within one scene** until each clip reaches 4-8s. The timeline is preserved exactly - no shot is dropped, stretched or reordered, and the clips sum to the storyboard's total. *Lead's call among three options.*
  3. **Scene boundaries are never crossed.** A scene change is a hard cut; one clip spanning it would ask the provider to render two unrelated places at once. The cost is that a scene which cannot be split evenly yields one short clip - a 9s scene of 3s shots can only be 6+3 - so **the CLI reports how many clips fall under the minimum** rather than hiding it.
  4. **The provider contract becomes `generate(request, references)`** per the spec. `ClipReferences` carries the character stills, the scene still and the **previous clip**, so a provider that supports continuation can carry the look forward. A provider supporting none of them ignores it - the contract offers references, it does not require their use. Mock and Kling both updated; Kling conditions on `references.primary`.
  5. **Clips are named `shot_NNN.mp4`** as specified, numbered by clip. The manifest records `clip_id` and the `shot_ids` each clip covers, so the merge is auditable.
  6. **`--resume` reuses clips already on disk** without re-spending; **`--storyboard`** selects the new route while `--movie` keeps Sprint 021's scene-per-clip path working.
- **Consequences:** `video generate --storyboard` produces one addressable clip per 4-8s run of shots, with references wired for consistency. Director, storyboard and compose are untouched. Verified against the real storyboard: 30 shots -> 20 clips, 90.0s preserved, portrait 1080x1920, scene stills resolving to the generated images.
- **Known gaps (both reported, neither hidden):** half the real storyboard's clips are 3s because 9s scenes of 3s shots cannot split evenly - longer shots from `director` would fix it upstream. And **character reference images are always empty**: `CharacterProfile.reference_image` has been `None` since Sprint 019, so identity currently reaches the provider through prompt text alone. The plumbing is in place for when those stills exist.
- **Alternatives considered:** Clamping each shot up to 4s - rejected by the Lead: it silently desyncs a 90s timeline to 120s. Honouring shot durations exactly - rejected: it ignores the stated 4-8s band. Crossing scene boundaries to avoid short clips - rejected: a clip containing a hard cut is worse than a short clip.

---

### ADR-037 - Visual Continuity Engine
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** Generated stills drifted between shots - different faces, clothing, colour and light - because each image prompt described only its own shot. Sprint 025B fixes the *prompt*, not the provider. Two spec inputs did not exist (`character_bible.json`, `world_bible.json`) and one named output (`image_prompts.json`) is already owned by the `image` stage; both were settled with the Lead before building.
- **Decision:**
  1. **The bibles are derived, then written out.** `character_bible.json` restates the character library (ADR-026) split into appearance / wardrobe / props; `world_bible.json` is assembled from the movie's style, genre and location descriptions. Deriving keeps them reproducible and free. Once on disk they are ordinary JSON: **a later run reads them back and never overwrites hand edits**, which is where richer art direction belongs. *Lead's call over LLM-authoring them.*
  2. **Prompts go to a new file.** `shot_image_prompts.json` holds one prompt per shot in the **existing** `ImagePrompt` schema, so a later sprint can point the `image` stage at it without a migration, while `image_prompts.json` stays exactly as the `image` stage left it. *Lead's call - nothing downstream breaks today.*
  3. **A prompt is never built from its own shot alone.** Every prompt carries the character bible, the world bible, the visual context, the previous / current / next shot, camera, lens, lighting, art direction, cinematic style and negatives.
  4. **Continuity is asserted only within a scene.** Across a scene cut the world may legitimately change; claiming continuity there would fight the story. `VisualContext.is_scene_opening` marks the boundary and the composer omits backwards directives at it.
  5. **Regeneration escalates explicitness rather than rerolling.** The composer has three levels: state each element, then add imperative continuity directives, then repeat identity verbatim. A prompt below the threshold is recomposed one level higher - so a retry genuinely changes the text and can change the outcome.
  6. **The scorer measures coverage, and counts missing source data against the score.** An element the storyboard never recorded still lowers the score, because a storyboard with no weather really does produce images whose weather drifts. `issues` names what was missing, so a low score points at the upstream gap.
- **Consequences:** Prompts now average **93/100** on the real 30-shot storyboard, with the shortfalls named (`weather`, `props`, `previous_camera` on the opening shot). Nothing downstream changed: no provider, no video stage, no compose, and `image_prompts.json` is untouched. **Nothing consumes `shot_image_prompts.json` yet** - wiring the image stage to it is a later sprint's call.
- **A scorer that always returns 100 was caught and rewritten.** The first version excluded absent data from the denominator, so every prompt scored a perfect 100 and the regeneration path was dead code. Counting absent data as a real deduction made the score diagnostic and the escalation loop live.
- **Alternatives considered:** LLM-authored bibles - rejected by the Lead: a derived bible is reproducible and free, and hand editing covers the gap. Overwriting `image_prompts.json` - rejected: it would silently change what `image` generates and what the video stage finds. Looping regeneration until the score passes - rejected: when the cause is missing upstream data no rephrasing can fix it, so the shortfall is reported instead.

---

### ADR-038 - Character Memory Engine
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** Sprint 025B made consecutive *frames* match; a character still drifted between images because nothing remembered what they had already been rendered as. Sprint 025C freezes each character's look and makes every later prompt restate it. The constraints ruled out touching a provider, so image-to-image conditioning is out of reach and the reference must reach the model as words.
- **Decision:**
  1. New `output/character_memory.json` holds every documented field per character (`canonical_face`, `canonical_hair`, `canonical_body`, `canonical_clothes`, `canonical_weapon`, `canonical_expression`, `canonical_color_palette`, `reference_image`, `appearance_hash`) plus `gender`, `age` and `style`, which the validator compares but the spec's field list omitted.
  2. **The canon is derived once, then frozen.** A later run reloads the memory and **never overwrites a remembered value** - only fills fields that were empty and adds new characters. A look that changes between runs is precisely the drift this stage exists to stop, so re-derivation would defeat it. Hand edits survive for the same reason.
  3. **The first image that exists for a character becomes its reference**, chosen by walking the storyboard in timeline order. Once adopted it is **never replaced** - re-pointing it at a later image would silently redefine the character mid-film. Adoption is by *existence* rather than by hooking image generation, which would have meant modifying a stage this sprint does not own.
  4. **`appearance_hash`** fingerprints the canonical fields. If the stored hash stops matching the stored appearance, the look has been changed without acknowledgement and every image already rendered is stale - the CLI says so.
  5. **`AppearanceValidator`** scores eight attributes (hair, face, clothes, weapon, colours, gender, age, style). An attribute the memory never captured scores **0**, not "not applicable": a character with no recorded weapon really will grow different ones, and excusing the gap would report a perfect score for a prompt that pins nothing. `issues` marks those as `(not remembered)` so the cause is unambiguous.
  6. **Below the threshold the prompt is rebuilt more insistently** - state the summary, then lock identity, then pin every attribute individually. The same escalation the continuity engine uses, so a retry genuinely changes the text.
  7. **Reference handling is provider-aware but provider-agnostic.** `PROVIDERS_WITH_IMAGE_REFERENCE` is empty today because no shipped image driver accepts one and this sprint may not change a provider; the reference is therefore described in words. A driver that gains the capability is added to that set and the path is attached instead - no other code changes.
- **Consequences:** Prompts now restate a frozen identity, average **97/100** on the real film. Backward compatible: the memory stage reads and rewrites `shot_image_prompts.json` (Sprint 025B's own output, which nothing consumes yet) and leaves `image_prompts.json`, the providers, the video stage and compose untouched. New CLI `ai-video-factory character memory`.
- **Known gap:** only `diep_pham` has a reference image, because `output/images/` holds six stills generated from the *old* per-scene prompts. The other three adopt one as soon as an image exists for their shots. The standing score deduction is `weapon (not remembered)` for characters whose bible records no weapon - fixable by editing the bible or the memory.
- **Alternatives considered:** Hooking the `image` command so generation itself records the canonical reference - rejected: it modifies a stage outside this sprint's remit, and adoption-by-existence reaches the same end state. Excusing unrecorded attributes in the score - rejected for the same reason it was rejected in ADR-037: it produces a flattering number that hides the actual problem.

---

### ADR-039 - Cinematic Director
- **Status:** Superseded by ADR-040 (the `cinema` module and command remain working; `shot-plan` is the path to use)
- **Date:** 2026-07-20
- **Context:** The prompts produced through Sprint 025C were consistent but not *directed*: every shot was described the way a prompt writer describes a picture, not the way a director calls a setup. Two symptoms were concrete. Almost every shot resolved to an 85mm portrait lens, because `_lens_for()` inferred a lens from the word "close" in the storyboard's camera string. And subjects were repeatedly "standing" - a description that gives an image generator nothing to compose and a video model nothing to move.
- **Decision:**
  1. A new `cinema` stage sits between the storyboard and the prompts. `SceneDirector` decides what each scene is *for* (purpose, emotion, conflict, story beat); `ShotDirector` decides how each shot is *filmed* (shot type, camera angle, lens, composition, blocking, lighting, action, motion hint). Both are pure - the vocabulary and its rules live in `infrastructure/cinema/vocabulary.py`, the value objects in `domain/value_objects/cinema.py`.
  2. **The choice is deterministic, not model-authored.** Coverage is a set of craft rules, and rules that are written down can be tested; the same storyboard must yield the same shot list. No LLM call, no cost, no variance.
  3. **85mm is never a default, structurally.** A lens is chosen from a table keyed by shot size, and 85mm appears only under `close up` and `extreme close up` - and never alone there, always alternating with 135mm. The rule cannot be violated by a bad inference because inference was removed: `compose_prompt` now prefers the director's decision over `_lens_for()`.
  4. **Lens alternation counts per shot size, not per global position.** The first version indexed by the shot's position in the film, so close ups all landed on the same parity and 135mm was unreachable. Counting uses of each size fixed it: the real film now covers 24mm x12, 35mm x7, 50mm x5, 85mm x3, 135mm x3.
  5. **The coverage cycle is offset by the scene's position.** Without the offset every scene of equal length is filmed shot-for-shot identically - a template rather than direction. The offset is what makes scene two differ from scene one.
  6. **A static action is replaced, not decorated.** `activate()` substitutes an active verb (walking, running, drawing a sword, casting a spell, ...) only when the description is genuinely static; a description that already carries a verb is kept, because the writer's own words beat a generic substitute.
  7. **Conflict is left empty when nothing states it.** `infer_conflict` reads the emotional register, then what the characters do, and returns `""` if neither says anything - naming a conflict nobody wrote would be invention rather than direction.
  8. `PromptComposer` is rewritten to the director's order - Character, Environment, Action, Camera, Composition, Lighting, Lens, Motion Hint, Negative - with the Sprint 025B continuity sections folded in. `direction` is optional, so every existing caller composes exactly as before.
- **Consequences:** New CLI `ai-video-factory cinema --storyboard output/storyboard.json`, writing `cinematic_direction.json` and rewriting `shot_image_prompts.json`. Coverage on the real film spans six shot types and five lenses. Backward compatible: no provider, video or compose change, and `image_prompts.json` is untouched. **`shot_image_prompts.json` is shared with Sprints 025B/C**, so running `cinema` replaces the continuity engine's prompts - the CLI warns, and says to re-run `character memory` afterwards to restore the frozen-identity block.
- **Alternatives considered:** Asking the LLM to direct each shot - rejected: it costs a request per movie for a decision that is rule-shaped, and it makes the shot list non-reproducible. Writing to a third prompt file - rejected: three files claiming to be "the shot prompts" is worse than one file with a documented owner. Emitting the emotion in both the direction and the light/motion sections - removed once seen; a duplicated line dilutes the prompt.

---

### ADR-040 - Cinematic Shot Planner
- **Status:** Accepted
- **Date:** 2026-07-20
- **Context:** The generated images came back as near-identical portraits. Measuring the pipeline rather than guessing found three causes, all upstream of the image provider: (1) the **storyboard itself** asks for `close-up` on 9 of 30 shots and `medium shot` on 9 more - 60% of the film is framed tight before any prompt is composed; (2) the prompts carried no statement of *what else must be in the frame*, so a model given a character and a mood drew a character on a backdrop; (3) nothing measured the film as a whole, so every individually-defensible close up summed to thirty portraits. **The 30 images on disk were generated before the Sprint 026 cinematic director ever ran** (21:56 against 22:18), so they were never evidence about ADR-039 - but the defects above are real regardless, and ADR-039 addressed only the third of them partially.
- **Decision:**
  1. New `ShotPlanner` stage: `storyboard.json` (+ `movie_directed.json`, `world_bible.json`) -> **`output/shot_plan.json`** and **`output/shot_statistics.json`**. Every shot carries all sixteen specified fields, including a `reason`.
  2. **Coverage follows content.** Each scene is classified from its own words - opening, conversation, action, combat, emotion, landscape - and the sprint's rule for that kind sets the size the scene **opens on**; the rest of the scene walks that kind's coverage pattern. Read strictly ("conversation → medium" for *every* shot) the rule would reproduce the monotony it exists to remove, so it is enforced as *the mandated size leads and dominates its scene*. This is an interpretation and is flagged as one.
  3. **The film is validated as a distribution**, not shot by shot: close <=20%, medium 20-35%, wide/full body >=40%, establishing >=5%. An invalid plan is **re-planned automatically**, demoting the *least justified* shot first - a size the scene's kind mandates is never traded away, so rebalancing cannot break the rule it is enforcing.
  4. **`close` counts `close_up` + `extreme_close` together.** The sprint lists them separately, but both produce a portrait, and the acceptance criterion is about portraits.
  5. **Every shot must state a foreground, midground or background**, derived from the shot's environment, the scene's location and the world bible. All three empty **rejects the shot** - that is exactly the shot that returns as a face on a blank backdrop. Nothing is invented: a depth with no source stays empty.
  6. **`PromptComposer` rewritten** to the specified order (Character, Environment, Action, Shot Type, Camera Distance, Camera Angle, Lens, Composition, Lighting, Motion Hint, Negative Prompt), because order is what a model weights - a prompt that opens on a face produces a face.
  7. **Portrait prevention runs both ways.** Close/portrait/headshot/face-focus language is stripped from the *source* text unless the plan approved a close size (the words are the storyboard's, so removing the phrase beats refusing the shot), and any that survives raises. Separately, a non-close shot **states the refusal in its own negative prompt** - telling a model what not to frame is more reliable than hoping the positive text outweighs its bias toward faces. The guard reads only the positive half of the prompt, or the protection would flag itself.
  8. **85mm can never be a default**: lenses come from a table keyed by shot size, reachable at 85mm only on the three closest sizes and alternating with 135mm there.
- **Consequences:** On the real 30-shot film: close **3.3%**, medium 33.3%, wide/full body **56.7%**, establishing 6.7%, valid after 3 automatic re-plans; body visibility **19 full body / 10 waist up / 1 head-and-shoulders**; lenses 35mm x13, 50mm x9, 24mm x6, 18mm x1, 85mm x1. New CLI `ai-video-factory shot-plan`. Deterministic and offline. No provider, video or compose change; `image_prompts.json` untouched.
- **Relationship to ADR-039:** This spec arrived under the same sprint number (026) and re-specifies the same problem more completely, so **the Shot Planner supersedes the Cinematic Director as the producer of `shot_image_prompts.json`**. ADR-039's `cinema` module and command are left working and tested rather than deleted - nothing was removed - but `shot-plan` is the path to use. Running both in either order is not meaningful; the last one run wins the prompts file.
- **Three defects were found and fixed during verification, two by the tests:** the re-plan cap was a fixed 12, so a badly-skewed 20-shot film needing 21 changes stopped half-way and reported itself "re-planned" while still 40% close ups (the cap now scales with the film); the negative prompt repeated the same boilerplate five times because de-duplication compared whole strings rather than terms; and `"golden"` was treated as a time of day, so a midnight cemetery lit by a phone screen was lit as golden hour.
- **Alternatives considered:** An LLM shot planner - rejected: coverage is rule-shaped, and a plan that changes between runs cannot be validated as a distribution. Rewriting `continuity/prompt_composer.py` in place - rejected: Sprints 025B and 025C depend on it, and the sprint requires backward compatibility, so the new composer lives beside it. Writing the prompts to a third file - rejected: three files each claiming to be "the shot prompts" is worse than one with a documented owner.

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
| 020 | Speech (TTS) provider layer | Accepted |
| 021 | Asset pipeline foundation | Accepted |
| 022 | Pollinations default image provider (free, key-less) | Accepted |
| 023 | Transcription provider layer for subtitle generation | Accepted |
| 024 | FFmpeg video composer (`compose`) | Accepted |
| 025 | Character & Scene Bible (Movie Builder) | Accepted |
| 026 | Character Consistency Engine (`character build` / `inject`) | Accepted |
| 027 | AI video provider layer (abstraction only) | Accepted |
| 028 | Kling AI video provider (first real video driver) | Accepted |
| 029 | Cost guard for paid video generation | Accepted |
| 030 | AI Director (cinematic shot planning) | Accepted |
| 031 | Director provider resilience (per-scene retry, partial, resume) | Partially superseded by 032 |
| 032 | Director plans the whole movie in one request | Accepted |
| 033 | Batch Director + Shot Planner | Accepted |
| 034 | OpenRouter as the director's LLM provider | Accepted |
| 035 | Storyboard Builder | Accepted |
| 036 | AI video generation from the storyboard | Accepted |
| 037 | Visual Continuity Engine | Accepted |
| 038 | Character Memory Engine | Accepted |
| 039 | Cinematic Director | Superseded by ADR-040 |
| 040 | Cinematic Shot Planner | Accepted |
