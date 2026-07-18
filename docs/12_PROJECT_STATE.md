# 12 — PROJECT STATE (Single Source of Truth)

> **⚠ READ THIS FILE FIRST before continuing any development.**
> This is the authoritative, always-current snapshot of the project. Where this file and any other document disagree about *current state*, this file wins. Where this file and the Architecture Document disagree about *structure*, the Architecture Document wins — and this file must be corrected.

**Purpose:** The one place that answers "where are we right now?" — version, sprint, what's done, what's in progress, what's next, what's blocked, and the live configuration of providers and modules. Every session begins here.

**Owner:** Technical Lead (updated by whoever advances the work).

**When to update:** At the **start and end of every working session** and at every sprint boundary. Keep it terse and factual. Keep `01_AI_CONTEXT.md` consistent with it.

**Last updated:** 2026-07-18

> **Sprint numbering note:** The executing plan from the Lead labels the foundation work **"Sprint 001 — Project Foundation"** (bootstrap + config + logging + CLI + exceptions + tests + tooling). This differs from the roadmap's Sprint 001 ("Domain Core"); the foundation was implemented per the Lead's explicit spec. Roadmap re-alignment, if desired, is the Lead's call.

---

## 1. Current Version

`0.1.0-dev` (foundation delivered; targeting `0.1.0` tag at end of the foundation milestone)

## 2. Current Sprint

**Sprint 001 — Project Foundation — DELIVERED** (per Lead spec; see also `03_ROADMAP.md`)

## 3. Completed

- Architecture Document (canonical) — **done**.
- Full documentation set in `docs/` (`00`–`13`, `CHANGELOG`) — **done**.
- ADR-001 … ADR-011 recorded — **done**.
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

`feat/sprint001-foundation`. `main` is protected.

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

## 8. Modules (layer readiness)

| Layer | Package | Status |
|---|---|---|
| Domain | `src/ai_video_factory/domain/` | package marker only (populated Sprint 002+) |
| Application | `src/ai_video_factory/application/` | package marker only (populated Sprint 002+) |
| Infrastructure | `src/ai_video_factory/infrastructure/` | **config, logging, diagnostics** implemented |
| Interface | `src/ai_video_factory/interface/` | **cli, presenters** implemented |
| Shared | `src/ai_video_factory/shared/` | package marker only |

## 9. Current Tasks

- [x] `src/` layout + Clean Architecture layer packages created.
- [x] Configuration, logging, exceptions, CLI (`version`, `doctor`), diagnostics implemented.
- [x] Ruff + MyPy(strict) + Pytest configured and passing (30 tests).
- [x] `pyproject` packaging produces the `factory` console script (`factory version`, `factory doctor` verified).

## 10. Next Tasks

- Await next Sprint spec from the Lead. Per roadmap, the natural next increment is the **Domain Core** (entities, value objects, enums) — not to be implemented until specified.

## 11. Known Issues

- `factory doctor` reports **FFmpeg: FAIL** on machines without ffmpeg installed (expected — ffmpeg is a documented runtime dependency, `08_ENVIRONMENT.md`). Not a code defect.
- import-linter is not yet wired as an automated gate (layer boundaries currently upheld by construction/review). Tracked for a later tooling pass.

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
| Sprint | 001 — Project Foundation (delivered) | 2026-07-18 |
| Roadmap progress | ~10% | 2026-07-18 |
| Stages implemented | 0 / 6 | 2026-07-18 |
| Providers wired | 0 | 2026-07-18 |
| Ports with contract tests | 0 / 7 | 2026-07-18 |
| Tests | 30 passing | 2026-07-18 |
| Open tech-debt items | 6 | 2026-07-18 |
| Gates (Ruff / MyPy / Pytest) | all green | 2026-07-18 |

---

### Update discipline

At every session end, refresh: **Current Sprint, Completed, In Progress, Current Branch, Current/Next Tasks, Known Issues, Blocked By, Roadmap Progress, Metrics, Last updated**. Then update `13_SESSION_HANDOFF.md` and, at sprint close, `01_AI_CONTEXT.md` and `CHANGELOG.md`.
