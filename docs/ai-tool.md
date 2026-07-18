AI Video Factory — Architecture Document

Version: 1.0 (MVP baseline)
Target runtime: Python 3.13, async-first
Scope: Idea → Story → Scene → Image → Voice → Subtitle → Video → MP4
Constraints honored: Clean Architecture · SOLID · Pydantic v2 · SQLAlchemy 2 · SQLite · Config-driven · Replaceable AI providers · CLI-first · No Web UI · No FastAPI · No Docker (yet)

---
1. Design Philosophy

The system is a pipeline of transformations, each step converting one artifact into the next. Two forces shape every decision:

1. The domain is stable, the providers are volatile. "A story has scenes; a scene has an image, a voice track, and subtitles" will be true for years. The specific model that draws the image or synthesizes the voice will change many times. Therefore the domain sits at the center and providers sit at the replaceable edge.
2. Each stage is independently ownable. Image generation, voice synthesis, and rendering evolve on separate clocks. The architecture must let one stage be rewritten, re-run, or swapped without touching the others.

The result is a Clean Architecture with a workflow engine driving a pipeline of stages, where every external capability (AI model, filesystem, ffmpeg, database) is hidden behind an interface owned by the domain.

---
2. Layered Architecture

Four concentric layers. Dependencies point inward only. Nothing in an inner layer may import from an outer layer.

┌─────────────────────────────────────────────────────────────┐
│  INTERFACE LAYER          (CLI, entrypoints, DI composition)  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  INFRASTRUCTURE LAYER   (providers, persistence, ffmpeg)│  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │  APPLICATION LAYER  (use cases, workflow, ports) │  │  │
│  │  │  ┌───────────────────────────────────────────┐  │  │  │
│  │  │  │  DOMAIN LAYER   (entities, value objects,  │  │  │  │
│  │  │  │                 domain rules, contracts)   │  │  │  │
│  │  │  └───────────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

           dependency direction  ───────────────▶  inward

2.1 Domain Layer (innermost — the core)

Purpose: Express what the business is, independent of how anything is done.

Contains:
- Entities — objects with identity and a lifecycle: Project, Story, Scene, MediaAsset (image/voice/subtitle), VideoRender.
- Value Objects — immutable, identity-less concepts: Idea, Prompt, Duration, Resolution, AspectRatio, LanguageCode, SubtitleCue, FilePath.
- Domain enums/state — PipelineStage, StageStatus (PENDING, RUNNING, COMPLETED, FAILED, SKIPPED).
- Domain services — pure logic that spans entities (e.g. subtitle timing alignment, scene splitting rules).
- Ports (abstract contracts) — the interfaces the outer world must satisfy: StoryGenerator, SceneBuilder, ImageProvider, VoiceProvider, SubtitleProvider, VideoComposer, and repository interfaces.
- Domain exceptions — DomainError and its descendants.

Rules:
- Zero third-party imports except the standard library and Pydantic (used strictly for validated value objects/DTOs).
- No I/O, no await on external systems, no SQLAlchemy, no HTTP, no ffmpeg.
- Knows nothing about SQLite, OpenAI, ElevenLabs, or any concrete technology.

▎ The domain is where the pipeline concept lives; the domain is never where a provider lives.

2.2 Application Layer (use cases + orchestration)

Purpose: Coordinate the domain to accomplish user goals. This is where the pipeline is executed.

Contains:
- Use cases / interactors — one class per user-meaningful operation: GenerateStory, BuildScenes, GenerateSceneImage, SynthesizeVoice, GenerateSubtitles, ComposeVideo, and the top-level RunPipeline.
- Workflow engine — the Pipeline and PipelineStep abstractions that sequence stages, manage state transitions, checkpoint progress, and enforce idempotency/resumability.
- Port definitions may live here too — application-specific ports (e.g. UnitOfWork, Clock, EventPublisher) that are broader than pure domain contracts.
- DTOs / command objects — Pydantic models describing the inputs/outputs of each use case.

Rules:
- Depends only on the Domain layer (entities + ports).
- Never instantiates a concrete provider or repository — it receives them via constructor injection as abstract ports.
- Contains no print, no SQL, no filesystem paths hardcoded, no HTTP client.
- Owns transaction boundaries via a UnitOfWork port (one workflow run = a coordinated set of transactions).

2.3 Infrastructure Layer (the replaceable edge)

Purpose: Implement the ports with real technology.

Contains:
- AI provider adapters — concrete ImageProvider, VoiceProvider, StoryGenerator implementations wrapping external SDKs/APIs.
- Persistence — SQLAlchemy 2 models, mappers, repository implementations, SQLite session/engine setup, Alembic migrations.
- Media/system adapters — ffmpeg wrapper (VideoComposer), file storage (AssetStorage), subtitle (.srt/.vtt) writers.
- Cross-cutting adapters — logging setup, config loader, HTTP client factory, retry/backoff, rate limiting, caching.

Rules:
- Depends on Application and Domain (it implements their interfaces).
- Nothing in the inner layers may import infrastructure. The dependency is satisfied at runtime through injection, not at import time.
- Each adapter maps external errors → domain/application exceptions at the boundary. External exception types never leak inward.

2.4 Interface Layer (delivery + composition root)

Purpose: Translate the outside world (a human at a terminal) into use-case invocations, and assemble the object graph.

Contains:
- CLI — command definitions (factory generate, factory resume, factory status, factory render), argument parsing, output formatting.
- Composition Root / DI container — the only place where concrete classes are wired to ports. Reads config, selects providers, constructs repositories, injects everything into use cases.
- Presenters — turn use-case results into terminal output (tables, progress, JSON).

Rules:
- The composition root is the single location aware of every concrete type. This isolates the "dirty" wiring knowledge to one edge.
- CLI commands are thin: parse → build command DTO → invoke use case → present result. No business logic.

---
3. Dependency Direction (the single most important rule)

Source-code dependencies always point inward. Control flow may point outward via interfaces (Dependency Inversion).

- Domain defines ImageProvider (an abstract port).
- Infrastructure's ReplicateImageProvider implements ImageProvider — so infrastructure depends on domain, never the reverse.
- Application calls ImageProvider.generate(...) at runtime, holding an instance it was given. It depends on the abstraction, not the implementation.

This is the Dependency Inversion Principle applied at the architectural scale:

Application  ──uses──▶  ImageProvider (port, in Domain)
                              ▲
                              │ implements
Infrastructure ──────────────┘   (ReplicateImageProvider)

Wiring happens once, at the Interface layer's composition root.

Consequences:
- You can delete an entire provider package and the domain/application still compiles.
- You can unit-test a use case with a fake provider — no network, no ffmpeg, no DB.
- Swapping SQLite for Postgres later touches only infrastructure + config.

Enforcement: import-linter (or equivalent) contracts in CI forbidding inward layers from importing outward packages. This is a checked rule, not a convention.

---
4. Package Structure & Responsibilities

ai_video_factory/
│
├── domain/                     # Layer 1 — pure core, no I/O
│   ├── entities/               #   Project, Story, Scene, MediaAsset, VideoRender
│   ├── value_objects/          #   Idea, Prompt, Duration, Resolution, SubtitleCue…
│   ├── enums/                  #   PipelineStage, StageStatus, AssetKind
│   ├── services/               #   pure domain logic (scene splitting, subtitle timing)
│   ├── ports/                  #   abstract contracts (providers + repositories)
│   └── errors.py               #   DomainError hierarchy
│
├── application/                # Layer 2 — orchestration
│   ├── use_cases/              #   GenerateStory, BuildScenes, ComposeVideo, RunPipeline…
│   ├── workflow/               #   Pipeline, PipelineStep, StageResult, checkpointing
│   ├── ports/                  #   UnitOfWork, Clock, EventPublisher, IdGenerator
│   ├── dto/                    #   command/result Pydantic models
│   └── errors.py               #   ApplicationError hierarchy
│
├── infrastructure/             # Layer 3 — concrete implementations
│   ├── providers/
│   │   ├── story/              #   LLM-backed StoryGenerator adapters
│   │   ├── image/              #   image model adapters
│   │   ├── voice/              #   TTS adapters
│   │   └── subtitle/           #   subtitle generator adapters
│   ├── persistence/
│   │   ├── models/             #   SQLAlchemy 2 ORM models (separate from entities)
│   │   ├── repositories/       #   repository implementations
│   │   ├── mappers/            #   entity ⇄ ORM translation
│   │   ├── unit_of_work.py     #   SQLAlchemy UoW
│   │   └── migrations/         #   Alembic
│   ├── media/
│   │   ├── ffmpeg/             #   VideoComposer implementation
│   │   └── storage/            #   AssetStorage (filesystem)
│   ├── config/                 #   Settings models + loaders (env + files)
│   ├── logging/                #   structured logging setup
│   └── clients/                #   HTTP client factory, retry, rate limiting
│
├── interface/                  # Layer 4 — delivery
│   ├── cli/                    #   command definitions + argument parsing
│   ├── presenters/             #   terminal/JSON output formatting
│   └── container.py            #   composition root / DI wiring
│
├── shared/                     # cross-cutting, dependency-free helpers
│   ├── result.py               #   Result/Either type if used
│   ├── types.py                #   shared type aliases, NewTypes
│   └── constants.py
│
└── main.py                     # thin entrypoint → interface.cli

Key responsibility boundaries:

┌────────────────┬────────────────────────────────────────────────────────┬──────────────────────────────────────┐
│    Package     │                          Owns                          │           Must NOT contain           │
├────────────────┼────────────────────────────────────────────────────────┼──────────────────────────────────────┤
│ domain         │ Business concepts, rules, contracts                    │ I/O, frameworks, provider names      │
├────────────────┼────────────────────────────────────────────────────────┼──────────────────────────────────────┤
│ application    │ Use cases, workflow sequencing, transaction boundaries │ Concrete providers, SQL, CLI parsing │
├────────────────┼────────────────────────────────────────────────────────┼──────────────────────────────────────┤
│ infrastructure │ Real adapters, DB, ffmpeg, HTTP                        │ Business rules, CLI                  │
├────────────────┼────────────────────────────────────────────────────────┼──────────────────────────────────────┤
│ interface      │ CLI, presentation, DI wiring                           │ Business logic                       │
├────────────────┼────────────────────────────────────────────────────────┼──────────────────────────────────────┤
│ shared         │ Framework-free utilities                               │ Anything depending on inner layers   │
└────────────────┴────────────────────────────────────────────────────────┴──────────────────────────────────────┘

Domain entities vs. ORM models are deliberately separate (no "active record"). Entities are pure; SQLAlchemy models live in infrastructure; mappers translate between them. This prevents persistence concerns from leaking into the domain and lets the storage engine change freely.

---
5. Coding Standards

- Python 3.13, async-first. All I/O-bound operations (provider calls, DB, file writes) are async. CPU-bound/blocking work (ffmpeg subprocess) is dispatched via asyncio.to_thread / subprocess so the event loop is never blocked.
- Strong typing everywhere. Full type hints on every function signature. mypy --strict (or pyright strict) is a CI gate. No untyped dict flowing across boundaries — use Pydantic models or dataclasses. Use NewType for identifiers (ProjectId, SceneId) to prevent accidental mixing.
- Pydantic v2 for all data at boundaries — config, DTOs, provider request/response schemas, value objects that need validation. Domain entities may be Pydantic models or frozen dataclasses; value objects are immutable (frozen=True).
- SOLID enforced structurally:
  - SRP — one class, one reason to change. Use cases do one operation.
  - OCP — new provider = new class implementing an existing port; no edits to existing code.
  - LSP — every provider is fully substitutable behind its port; no adapter throws "not supported" for a port method it declares.
  - ISP — ports are narrow and role-specific (ImageProvider ≠ a god "AIProvider" interface).
  - DIP — depend on ports, inject implementations.
- Immutability by default. Prefer frozen value objects; entities mutate only through explicit intention-revealing methods.
- No global mutable state. No module-level singletons holding sessions or clients. Everything is constructed in the composition root and injected.
- Small, composable functions. Pure functions in the domain; side effects pushed to the edges.
- Formatting/linting: ruff (lint + format), mypy/pyright strict, import-linter for layer boundaries — all enforced in CI, not left to discipline.
- Docstrings on every public port and use case describing the contract (pre/postconditions, raised exceptions), not the implementation.

---
6. Naming Conventions

- Packages/modules: snake_case, singular for concepts (domain.entities.scene), plural only for collection packages (use_cases, providers).
- Classes: PascalCase.
- Functions/variables: snake_case. Constants: UPPER_SNAKE_CASE.
- Ports (interfaces): named by role/capability, no I-prefix — ImageProvider, StoryGenerator, VoiceProvider, VideoComposer, ProjectRepository.
- Implementations: named by the technology or vendor they wrap + the port role — FfmpegVideoComposer, SqlAlchemyProjectRepository, ElevenLabsVoiceProvider, OpenAiStoryGenerator. The name tells you exactly what it is.
- Use cases: verb-phrase describing the action — GenerateStory, ComposeVideo, RunPipeline. Their entrypoint method is execute(command) -> result.
- DTOs: <Action>Command / <Action>Result (GenerateStoryCommand, ComposeVideoResult).
- Value objects: noun for the concept (Duration, Resolution, SubtitleCue).
- Enums: singular noun, PascalCase members or UPPER_SNAKE — pick one and apply everywhere (recommend UPPER_SNAKE for members).
- Async functions carry no special prefix; the signature declares it.
- Test names: test_<unit>_<condition>_<expected_outcome>.
- Booleans: is_, has_, should_ prefixes.

Consistency is enforced by ruff naming rules where possible; the rest is captured in CONTRIBUTING/CLAUDE.md.

---
7. Error Handling

A layered exception hierarchy, translated at every boundary.

AppError (root)
├── DomainError            # rule violations: InvalidSceneError, EmptyStoryError
├── ApplicationError       # use-case/workflow: StageFailedError, PipelineAbortedError
├── InfrastructureError    # adapter failures
│   ├── ProviderError      # ImageProviderError, VoiceProviderError…
│   ├── PersistenceError
│   └── MediaError         # ffmpeg failures
└── ConfigurationError     # invalid/missing config (fail fast at startup)

Principles:
- Translate at boundaries. Infrastructure catches vendor exceptions (httpx.HTTPError, SDK errors, subprocess failures) and re-raises as domain-meaningful ProviderError/MediaError. Raw third-party exceptions never propagate into application or domain code.
- Errors are typed and specific, not stringly-typed. Each exception carries structured context (which stage, which scene id, which provider, retryable flag).
- Distinguish retryable vs. terminal. ProviderError(retryable=True) (rate limit, transient 5xx) triggers the retry policy; terminal errors fail the stage immediately.
- Fail fast on configuration. Invalid config raises ConfigurationError at startup, before any pipeline work begins — never mid-render.
- Never swallow. No bare except: pass. Every catch either handles, translates, or re-raises with context.
- Pipeline resilience: a failed stage marks that stage FAILED, persists the error, and stops the affected pipeline branch. Because state is checkpointed, the user can fix the cause and resume from the failed stage rather than restarting from the idea.
- CLI boundary is the final catch: unhandled AppError → clean, formatted message + non-zero exit code; unexpected Exception → logged with full traceback + generic failure message. Tracebacks go to logs, not to a confused user (unless --verbose).
- Result vs. exceptions: exceptions for exceptional/unexpected failures; explicit StageResult/status objects for expected outcomes (a scene skipped, a stage already complete). Control flow is not driven by exceptions.

---
8. Configuration Management

Config-driven and layered, validated by Pydantic v2.

- Single typed settings tree — a root Settings model composed of nested sections: AppSettings, DatabaseSettings, LoggingSettings, PipelineSettings, and ProviderSettings (image/voice/story/subtitle/video).
- Precedence (highest wins): explicit CLI flags → environment variables → .env file → config file (config.toml/yaml, per-environment) → in-code defaults.
- Provider selection is config, not code. Each stage's active provider is chosen by a key in config:
[providers.image]
driver = "replicate"        # ← selects which adapter the container wires
model  = "flux-1.1-pro"
[providers.voice]
driver = "elevenlabs"
- The composition root reads driver and constructs the matching adapter via a provider registry/factory. Swapping a provider = editing one config value. No code change.
- Secrets (API keys) come only from environment variables / a secrets file, never committed, never in the DB, never logged. Pydantic SecretStr prevents accidental serialization.
- Environments (dev, test, prod) select different config files; the active one is chosen by APP_ENV.
- Validation at load time. The entire settings tree is parsed and validated once at startup; missing keys, wrong types, or an unknown driver fail immediately with a precise ConfigurationError.
- Config is injected, never read ad-hoc. No module reaches into os.environ on its own; only the config loader does. Components receive their own strongly-typed settings slice.

---
9. Logging Strategy

- Structured logging (JSON in prod, human-readable/colored in dev) via a single logging setup in infrastructure, configured from LoggingSettings.
- Correlation via context. Every pipeline run gets a run_id; every log line within a run carries run_id, project_id, stage, and where relevant scene_id/provider. Implemented with contextvars so async tasks propagate context without manual threading.
- Levels with intent:
  - DEBUG — provider payload sizes, prompts (with secrets redacted), timing.
  - INFO — lifecycle events: stage started/completed, artifact written, run finished.
  - WARNING — retryable failures, fallbacks, skipped scenes.
  - ERROR — stage failures, terminal provider errors.
  - CRITICAL — unrecoverable/config failures aborting the run.
- No secrets in logs, ever. A redaction filter scrubs API keys and SecretStr values.
- Loggers are injected/named per module (logging.getLogger(__name__)); no print anywhere except the presenter layer's deliberate user output.
- Observability-ready. Because logs are structured and correlated, they can later feed a log aggregator or metrics pipeline without refactoring. Timing/duration of each stage is logged to support future cost/performance analysis.
- Separation of concerns: logs are for the operator; CLI presenter output is for the user. They are distinct channels.

---
10. Testing Strategy

A pyramid, aligned to the layers:

- Domain unit tests (largest share, fastest). Pure functions and entities tested in isolation — no mocks needed, no I/O. Scene-splitting, subtitle-timing, value-object validation, state transitions. These are the fast, deterministic bedrock.
- Application/use-case tests. Each use case tested against fake/in-memory implementations of ports (fake ImageProvider, in-memory ProjectRepository, fake Clock). Verifies orchestration, workflow sequencing, error translation, resume/checkpoint logic — with zero network, zero ffmpeg, zero real DB. This is where the "async-first, injectable ports" design pays off.
- Contract tests for ports. A shared test suite runs against every implementation of a port to prove substitutability (LSP). Any new VoiceProvider must pass the same VoiceProvider contract tests. This is what makes providers safely replaceable.
- Infrastructure/integration tests (fewer). Real SQLite (temp file/in-memory) for repositories + migrations; real ffmpeg on tiny fixtures for the composer; provider adapters tested against recorded/mocked HTTP (VCR-style cassettes) so they don't hit paid APIs in CI.
- End-to-end/pipeline smoke tests. The full RunPipeline wired with cheap/fake providers, asserting a valid MP4 is produced and DB state is correct — proving the stages connect.
- Property-based tests (Hypothesis) for value objects and timing/alignment logic.

Standards:
- pytest + pytest-asyncio; async tests are first-class.
- Coverage gate on domain + application (the code that must never silently break); infrastructure coverage measured but weighted by risk.
- No test hits a paid external API or the network by default; live-provider tests are opt-in and marked.
- Tests depend on ports, not concretes — mirroring production wiring, so tests document the intended architecture.
- Fixtures build object graphs the same way the composition root does, keeping tests honest.

---
11. How Future Modules Plug In

The pipeline is deliberately open for extension, closed for modification. New capability is added, never patched in.

Two extension shapes:

A. A new provider for an existing stage (e.g. a new image model):
1. Add an adapter in infrastructure/providers/image/ implementing the existing ImageProvider port.
2. Register it in the provider registry under a driver key.
3. Select it via config.
No domain, application, or CLI change.

B. A new pipeline stage (e.g. add a "Music"/"Background Score" step, or "Thumbnail" generation):
1. Define the new port + entity/value objects in the domain (MusicProvider, MusicTrack).
2. Add a use case + a PipelineStep in the application layer and insert it into the workflow definition.
3. Implement the adapter in infrastructure.
4. Register + expose via CLI/config.

Because the workflow is config- and registry-driven (stages declared as an ordered, named list rather than hardcoded call chains), inserting a stage is a declarative change plus one new implementation — existing stages remain untouched. Each stage reads its inputs from persisted artifacts and writes its outputs back, so stages stay decoupled and independently runnable/resumable. Post-MVP concerns (queue-backed execution, parallel scene rendering, remote workers, a Web UI, HTTP API) attach at the interface/infrastructure edge without disturbing the core — e.g. a future FastAPI delivery layer would sit beside the CLI as another interface adapter calling the same use cases.

---
12. AI Provider Abstraction

This is the linchpin of "replaceable AI providers," and it is enforced by the layering, not by convention.

- One narrow port per capability, owned by the domain: StoryGenerator, SceneBuilder, ImageProvider, VoiceProvider, SubtitleProvider, VideoComposer. Each exposes only the methods that capability needs (ISP). There is no monolithic AIProvider — that would violate ISP and couple unrelated stages.
- Ports speak domain language, not vendor language. ImageProvider.generate(prompt: Prompt, spec: ImageSpec) -> ImageAsset — no mention of a model id, endpoint, or SDK type. Vendor-specific parameters live inside the adapter and its config, never in the port signature.
- Adapters translate both ways. Each adapter maps domain request → vendor request, and vendor response → domain artifact, and vendor error → ProviderError. The translation is the adapter's entire job.
- Selection is data-driven. A provider registry/factory maps a config driver string to a constructor. The composition root builds the chosen adapter and injects it. Adding/replacing a provider never edits existing code (OCP).
- Cross-cutting provider concerns are shared, not duplicated: retry/backoff, rate limiting, timeout, and response caching are implemented once as decorator adapters wrapping any provider (e.g. RetryingImageProvider(inner: ImageProvider)), composed at wiring time. A provider gets resilience for free by being wrapped, keeping each concrete adapter focused purely on translation.
- Substitutability is verified, not assumed — every provider passes its port's contract test suite (see §10). This is what lets you trust a swap in production.
- Cost/limits awareness lives in infrastructure (rate limiter, usage logging), never in the domain, so the core stays pure while operations stay controllable.

Net effect: the day a better image model appears, you write one adapter, add one config line, run the contract tests, and ship — with the rest of the system provably unaffected.

---
13. Workflow Execution

The pipeline is a first-class, explicit, resumable state machine, not an implicit chain of function calls.

- Declared, ordered stages. The workflow is defined as a named sequence: STORY → SCENES → IMAGE → VOICE → SUBTITLE → VIDEO. Each stage is a PipelineStep wrapping one use case, with declared inputs (prior artifacts) and outputs.
- Every stage is persisted and checkpointed. After each stage completes, its output artifacts and a StageStatus are written to SQLite within a transaction (via UnitOfWork). The DB is the source of truth for run progress.
- Idempotent and resumable. Re-running a project inspects persisted state and skips already-COMPLETED stages, resuming from the first incomplete/FAILED one. A crash mid-render never forces starting over from the idea. factory resume <project_id> continues; --force <stage> re-runs a specific stage.
- Async orchestration with controlled concurrency. Stages that operate per-scene (image, voice, subtitle) fan out across scenes with a bounded asyncio concurrency limit (from PipelineSettings) to respect provider rate limits. The final VIDEO stage joins all scene artifacts. Blocking work (ffmpeg) runs off the event loop.
- Explicit result objects. Each step returns a StageResult (status + produced artifact refs + optional error), so expected outcomes (skipped, already-done) are data, and only unexpected failures raise.
- Failure isolation. A failed scene marks that unit FAILED with structured context; the run reports partial progress and stops the affected branch, leaving completed work intact and resumable.
- Observable. Each stage emits correlated start/finish logs with timing and a domain event (via an EventPublisher port) — enabling a live CLI progress view now and metrics/queue integration later.
- Deterministic wiring, dynamic execution. The stage list and per-stage provider are resolved from config at startup; the engine executes generically over that list, so reordering or extending the pipeline is configuration, not surgery.

---
14. Keeping the Architecture Maintainable for Years

Maintainability here is a set of enforced invariants, not aspirations:

1. The dependency rule is machine-checked. import-linter contracts in CI fail the build if any inner layer imports an outer one. The most important architectural rule cannot silently erode.
2. The domain stays pure and dependency-free. Because business concepts have no framework/vendor imports, they age far slower than the tools around them. Volatility is pushed to the edge where it's cheap to replace.
3. Everything volatile hides behind a port. Providers, DB, ffmpeg, and delivery mechanism are all replaceable adapters. In years, you'll swap models, maybe the DB, maybe add an API — each is a contained change against a stable contract.
4. Contract tests guard substitutability. New implementations must satisfy the same tests, so replacements can't quietly break behavior.
5. Config-driven selection means fewer code changes over time. Provider/stage choices move at the speed of a config edit, and each edit is validated at startup.
6. Strict typing + strict linting as CI gates. mypy/pyright --strict, ruff, coverage thresholds, and layer contracts run on every change. Quality is enforced by the pipeline, not by reviewer memory.
7. Separation of entity vs. persistence model keeps storage decisions from calcifying into the domain, so migrating SQLite → Postgres later is a bounded infrastructure task.
8. Documented conventions live with the code. This document plus a CLAUDE.md/CONTRIBUTING.md capture naming, error, and layering rules so new contributors (human or AI) extend the system the intended way.
9. Small, single-responsibility units keep the blast radius of any change small and the codebase readable — the strongest long-term defense against rot.
10. Extension over modification. Every anticipated future (new provider, new stage, queue backend, Web UI, API) has a designated seam. Growth adds files; it doesn't rewrite the core.

The guiding principle: let the fast-changing parts change fast at the edges, and let the slow-changing core stay still. Sustained over years, that is what keeps AI Video Factory maintainable while models, vendors, and delivery channels churn beneath it.

---
Appendix A — Dependency & Data Flow (at a glance)

CLI command
   │  (parse → command DTO)
   ▼
Composition Root ── wires ──▶ concrete providers, repos, ffmpeg (from CONFIG)
   │  injects ports
   ▼
RunPipeline (application/workflow)
   │  executes ordered stages, checkpoints to SQLite
   ├─▶ GenerateStory ─── StoryGenerator (port) ──▶ [OpenAiStoryGenerator]
   ├─▶ BuildScenes ───── SceneBuilder    (port) ──▶ [LlmSceneBuilder]
   ├─▶ GenerateImage ─── ImageProvider   (port) ──▶ [ReplicateImageProvider]
   ├─▶ SynthesizeVoice ─ VoiceProvider   (port) ──▶ [ElevenLabsVoiceProvider]
   ├─▶ GenerateSubtitle─ SubtitleProvider(port) ──▶ [WhisperSubtitleProvider]
   └─▶ ComposeVideo ──── VideoComposer   (port) ──▶ [FfmpegVideoComposer] ──▶ MP4

   All ports defined in DOMAIN. All [brackets] live in INFRASTRUCTURE.
   Application never names a bracket. Direction of source dependency: inward.

Appendix B — Non-Goals for MVP (intentional deferrals with seams reserved)

- No Web UI / no FastAPI — delivery is CLI-only; a future HTTP layer attaches as a sibling interface adapter over the same use cases.
- No Docker yet — runtime is local; containerization is an operational concern outside the architecture and changes no source.
- No distributed queue/workers yet — the workflow engine's stage abstraction and EventPublisher port reserve the seam for later queue-backed execution.
- SQLite only — entity/ORM separation keeps a future engine swap contained to infrastructure.