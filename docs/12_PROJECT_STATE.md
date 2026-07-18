# 12 — PROJECT STATE (Single Source of Truth)

> **⚠ READ THIS FILE FIRST before continuing any development.**
> This is the authoritative, always-current snapshot of the project. Where this file and any other document disagree about *current state*, this file wins. Where this file and the Architecture Document disagree about *structure*, the Architecture Document wins — and this file must be corrected.

**Purpose:** The one place that answers "where are we right now?" — version, sprint, what's done, what's in progress, what's next, what's blocked, and the live configuration of providers and modules. Every session begins here.

**Owner:** Technical Lead (updated by whoever advances the work).

**When to update:** At the **start and end of every working session** and at every sprint boundary. Keep it terse and factual. Keep `01_AI_CONTEXT.md` consistent with it.

**Last updated:** 2026-07-18

---

## 1. Current Version

`0.1.0-dev` (pre-foundation; targeting `0.1.0` at end of Sprint 006)

## 2. Current Sprint

**Sprint 000 — Project Bootstrap & Tooling** (see `03_ROADMAP.md`)

## 3. Completed

- Architecture Document (canonical) — **done**.
- Full documentation set in `docs/` (`00`–`13`, `CHANGELOG`) — **done**.
- ADR-001 … ADR-010 recorded — **done**.

## 4. In Progress

- Sprint 000 deliverables: repository skeleton, tooling, CI gates (`BL-001`, `BL-002`).

## 5. Current Branch

`docs/sprint000-doc-set` (documentation); skeleton work on `feat/sprint000-bootstrap`.
`main` is protected.

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
| Domain | `domain/` | not started (Sprint 001) |
| Application | `application/` | not started (Sprint 002) |
| Infrastructure | `infrastructure/` | not started (Sprint 003+) |
| Interface | `interface/` | not started (Sprint 006) |
| Shared | `shared/` | not started (Sprint 000/001) |

## 9. Current Tasks

- [ ] `BL-001` Create package skeleton with import-linter contracts.
- [ ] `BL-002` Wire CI gates (ruff, mypy/pyright strict, import-linter, pytest).
- [ ] Confirm `pyproject`/packaging + editable install produces a `factory` entrypoint stub.

## 10. Next Tasks

- Sprint 001: Domain core (`BL-003`) — entities, value objects, enums, `DomainError` hierarchy.
- Sprint 002: Workflow engine (`BL-004`).

## 11. Known Issues

- None yet (no runtime code). Tech-debt items tracked in `10_TECH_DEBT.md`.

## 12. Blocked By

- Nothing. Sprint 000 has no external dependencies.

## 13. Roadmap Progress

```
[■□□□□□□□□□□□□□□□□□□□□]  Sprint 000 / 020   (5%)
Milestones: 0.1.0 (S006) · 0.2.0 (S008) · 0.5.0 (S013) · 0.9.0 (S019) · 1.0.0 (S020)
```

- Completed sprints: none (Sprint 000 in progress).
- Next milestone: `0.1.0` — Foundation, end of Sprint 006.

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
| Sprint | 000 / 020 | 2026-07-18 |
| Roadmap progress | 5% | 2026-07-18 |
| Stages implemented | 0 / 6 | 2026-07-18 |
| Providers wired | 0 | 2026-07-18 |
| Ports with contract tests | 0 / 7 | 2026-07-18 |
| Open tech-debt items | 6 | 2026-07-18 |
| Open critical backlog | 7 | 2026-07-18 |
| Test coverage (domain+app) | n/a (no code) | 2026-07-18 |
| CI status | pending first run | 2026-07-18 |

---

### Update discipline

At every session end, refresh: **Current Sprint, Completed, In Progress, Current Branch, Current/Next Tasks, Known Issues, Blocked By, Roadmap Progress, Metrics, Last updated**. Then update `13_SESSION_HANDOFF.md` and, at sprint close, `01_AI_CONTEXT.md` and `CHANGELOG.md`.
