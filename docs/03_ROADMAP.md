# 03 — ROADMAP

**Purpose:** The sprint-by-sprint plan from project bootstrap to the **v1.0** release. It sequences the work so the architecture is built from the inside out (domain → application → infrastructure → interface), then the pipeline stages are added one at a time, then hardened.

**Owner:** Technical Lead.

**When to update:** At sprint boundaries — when a sprint completes (mark done in `12_PROJECT_STATE.md`, not here), when scope is re-planned, or when acceptance criteria change. The roadmap defines intent; actual progress lives in `12_PROJECT_STATE.md`.

---

## Conventions

- One sprint ≈ one coherent architectural increment.
- Every sprint lists **Goal**, **Deliverables**, **Acceptance Criteria**, **Dependencies**.
- No stage is considered "done" until it is checkpointed, resumable, logged, tested, and passes its port contract tests where applicable.
- Version milestones: `0.1.0` (foundation), `0.2.0` (first stage e2e), `0.5.0` (all stages exist), `0.9.0` (full pipeline resumable), `1.0.0` (release).

---

## Sprint 000 — Project Bootstrap & Tooling
- **Goal:** Establish the repository skeleton, tooling, CI gates, and the full documentation set.
- **Deliverables:** Package skeleton (`domain/application/infrastructure/interface/shared`); ruff, mypy/pyright strict, pytest, import-linter configured; CI pipeline running all gates; this `docs/` set.
- **Acceptance Criteria:** CI is green on an empty skeleton; import-linter enforces layer contracts; `mypy --strict` passes; documentation index complete.
- **Dependencies:** None.

## Sprint 001 — Domain Core
- **Goal:** Model the domain purely.
- **Deliverables:** Entities (`Project`, `Story`, `Scene`, `MediaAsset`, `VideoRender`); value objects (`Idea`, `Prompt`, `Duration`, `Resolution`, `AspectRatio`, `LanguageCode`, `SubtitleCue`, `FilePath`); enums (`PipelineStage`, `StageStatus`, `AssetKind`); `DomainError` hierarchy; domain services stubs (scene splitting, subtitle timing contracts).
- **Acceptance Criteria:** Zero non-stdlib/Pydantic imports in `domain/`; domain unit tests pass; value objects immutable and validated.
- **Dependencies:** Sprint 000.

## Sprint 002 — Application Skeleton & Workflow Engine
- **Goal:** Define orchestration primitives.
- **Deliverables:** Use case base + `execute()` contract; `Pipeline`, `PipelineStep`, `StageResult`; application ports (`UnitOfWork`, `Clock`, `IdGenerator`, `EventPublisher`); command/result DTOs; `ApplicationError` hierarchy.
- **Acceptance Criteria:** Workflow engine sequences fake steps with checkpoint semantics using in-memory fakes; application tests pass with no infrastructure.
- **Dependencies:** Sprint 001.

## Sprint 003 — Persistence Foundation
- **Goal:** Real SQLite persistence behind repository ports.
- **Deliverables:** SQLAlchemy 2 ORM models; entity⇄ORM mappers; `SqlAlchemyProjectRepository`; SQLAlchemy `UnitOfWork`; Alembic migrations; engine/session setup.
- **Acceptance Criteria:** Integration tests against temp SQLite pass; migrations apply cleanly; entities never import SQLAlchemy.
- **Dependencies:** Sprint 001, 002.

## Sprint 004 — Configuration Management
- **Goal:** Config-driven settings tree.
- **Deliverables:** Pydantic `Settings` tree (`App`, `Database`, `Logging`, `Pipeline`, `Provider` sections); layered precedence (CLI > env > `.env` > file > defaults); `SecretStr` for keys; startup validation → `ConfigurationError`.
- **Acceptance Criteria:** Invalid config fails fast at startup; unknown `driver` rejected; secrets never serialized.
- **Dependencies:** Sprint 000.

## Sprint 005 — Logging & Observability
- **Goal:** Structured, correlated logging.
- **Deliverables:** Logging setup from `LoggingSettings`; `contextvars`-based `run_id`/`project_id`/`stage` correlation; secret redaction filter; per-stage timing logs; `EventPublisher` in-process implementation.
- **Acceptance Criteria:** JSON logs carry correlation fields; no secret appears in logs; DEBUG/INFO/WARNING/ERROR levels used per spec.
- **Dependencies:** Sprint 004.

## Sprint 006 — CLI Skeleton & Composition Root
- **Goal:** Delivery layer and DI wiring.
- **Deliverables:** CLI commands (`generate`, `resume`, `status`, `render`); argument parsing; presenters; `interface/container.py` composition root; provider registry scaffolding.
- **Acceptance Criteria:** `factory status` runs end-to-end against DB; container wires ports from config; CLI is thin (no business logic).
- **Dependencies:** Sprint 003, 004, 005.
- **Milestone:** `0.1.0` — Foundation complete.

## Sprint 007 — Provider Abstraction Framework
- **Goal:** The replaceable-provider machinery.
- **Deliverables:** Provider registry/factory (driver→constructor); decorator adapters `Retrying*`, `RateLimited*`, `Caching*`; HTTP client factory; error translation helpers.
- **Acceptance Criteria:** A fake provider is wired purely by config; decorators compose; retryable vs terminal errors honored.
- **Dependencies:** Sprint 006.

## Sprint 008 — Story Stage (end-to-end)
- **Goal:** Idea → Story working through the pipeline.
- **Deliverables:** `StoryGenerator` port finalized; `OpenAiStoryGenerator` adapter; `GenerateStory` use case + `PipelineStep`; CLI `generate` produces & persists a Story.
- **Acceptance Criteria:** `factory generate --idea "..."` yields a persisted Story; stage checkpointed and resumable; contract tests exist.
- **Dependencies:** Sprint 007.
- **Milestone:** `0.2.0` — First stage e2e.

## Sprint 009 — Scene Stage
- **Goal:** Story → Scenes.
- **Deliverables:** `SceneBuilder` port + `LlmSceneBuilder`; `BuildScenes` use case + step; scene-splitting domain service finalized.
- **Acceptance Criteria:** Scenes persisted with ordering and prompts; per-scene records ready for downstream fan-out; contract + domain tests pass.
- **Dependencies:** Sprint 008.

## Sprint 010 — Image Stage
- **Goal:** Scene → Image (per scene).
- **Deliverables:** `ImageProvider` port + `ReplicateImageProvider`; `GenerateSceneImage` use case; per-scene fan-out with bounded concurrency; image assets stored via `AssetStorage`.
- **Acceptance Criteria:** Each scene gets an image asset; concurrency respects rate limits; retries on transient errors; contract tests pass.
- **Dependencies:** Sprint 009.

## Sprint 011 — Voice Stage
- **Goal:** Scene → Voice narration.
- **Deliverables:** `VoiceProvider` port + `ElevenLabsVoiceProvider`; `SynthesizeVoice` use case; audio assets stored; duration captured for timing.
- **Acceptance Criteria:** Each scene gets a voice asset with measured duration; language honored; contract tests pass.
- **Dependencies:** Sprint 009.

## Sprint 012 — Subtitle Stage
- **Goal:** Scene/Voice → Subtitles.
- **Deliverables:** `SubtitleProvider` port + `WhisperSubtitleProvider`; `GenerateSubtitles` use case; `.srt`/`.vtt` writer; subtitle timing alignment domain service finalized.
- **Acceptance Criteria:** Subtitle cues aligned to voice timing; valid `.srt`/`.vtt` produced; contract + property tests pass.
- **Dependencies:** Sprint 011.

## Sprint 013 — Video Compose Stage
- **Goal:** Assets → MP4.
- **Deliverables:** `VideoComposer` port + `FfmpegVideoComposer`; `ComposeVideo` use case; ffmpeg subprocess adapter run off event loop; MP4 output with images + voice + subtitles.
- **Acceptance Criteria:** A valid MP4 is produced from fixtures; ffmpeg failures map to `MediaError`; contract test on tiny fixtures passes.
- **Dependencies:** Sprint 010, 011, 012.
- **Milestone:** `0.5.0` — All stages exist.

## Sprint 014 — Full Pipeline Orchestration
- **Goal:** One command, all stages, resumable.
- **Deliverables:** `RunPipeline` wiring all stages; checkpoint after each stage; `factory resume` and `--force <stage>`; end-to-end smoke test with fake providers.
- **Acceptance Criteria:** `factory generate` runs Idea→MP4; a crash mid-run resumes without redoing completed stages; e2e smoke green.
- **Dependencies:** Sprint 013.

## Sprint 015 — Concurrency & Rate-Limit Hardening
- **Goal:** Safe, efficient per-scene fan-out.
- **Deliverables:** Bounded concurrency from `PipelineSettings`; rate limiter tuning; partial-failure isolation per scene.
- **Acceptance Criteria:** N-scene projects render within provider limits; a single failed scene does not abort completed work.
- **Dependencies:** Sprint 014.

## Sprint 016 — Error Handling & Resilience Hardening
- **Goal:** Predictable failure behavior.
- **Deliverables:** Full exception hierarchy coverage; retryable/terminal classification across adapters; structured error context persisted; CLI exit codes.
- **Acceptance Criteria:** Every adapter translates vendor errors; failed stages persist actionable context; `--verbose` surfaces tracebacks, default does not.
- **Dependencies:** Sprint 015.

## Sprint 017 — Port Contract Test Suites
- **Goal:** Guaranteed substitutability.
- **Deliverables:** Shared contract test suite per port, run against every adapter and its fakes.
- **Acceptance Criteria:** Every provider passes its port's contract suite; adding a new adapter requires passing it.
- **Dependencies:** Sprints 008–013.

## Sprint 018 — Integration & E2E Test Hardening + CI
- **Goal:** Trustworthy test pyramid.
- **Deliverables:** VCR-style recorded provider tests; ffmpeg integration tests; full pipeline e2e with cheap/fake providers; coverage gates; CI matrix.
- **Acceptance Criteria:** No test hits paid APIs by default; coverage thresholds on domain+application met; CI green.
- **Dependencies:** Sprint 017.

## Sprint 019 — DX, Docs & Cost/Perf Logging
- **Goal:** Operability polish.
- **Deliverables:** Per-stage duration & (where available) cost logging; `factory status` rich output; docs refresh (`01`, `07`, `08`); troubleshooting guide.
- **Acceptance Criteria:** Operators can diagnose a run from logs alone; docs consistent with code.
- **Dependencies:** Sprint 018.
- **Milestone:** `0.9.0` — Full pipeline resumable & observable.

## Sprint 020 — v1.0 Release Hardening
- **Goal:** Ship 1.0.
- **Deliverables:** Packaging/entrypoint; version pinning; final acceptance run (Idea→MP4) on a real project; release notes in `CHANGELOG.md`; `12_PROJECT_STATE.md` set to `1.0.0`.
- **Acceptance Criteria:** A clean environment can install and produce an MP4 from an idea via CLI; all gates green; all ADRs current.
- **Dependencies:** Sprint 019.
- **Milestone:** `1.0.0` — Release.

---

## Post-1.0 Horizon (not scheduled here)

Publishing/distribution stage, additional provider adapters, parallel multi-project runs, queue-backed workers, and an HTTP delivery layer are **post-1.0**. Each attaches at the interface/infrastructure edge without changing the core (Architecture Document §11). Tracked in `11_BACKLOG.md`.
