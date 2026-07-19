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
