# 11 — BACKLOG

**Purpose:** The prioritized list of work items not yet scheduled into an active sprint — features, chores, and improvements categorized by priority. It is the pool from which sprints are populated and where new ideas land before they are planned.

**Owner:** Technical Lead.

**When to update:** Continuously — when new work is identified, when priorities shift, and when items are pulled into a sprint (move to `03_ROADMAP.md` / `12_PROJECT_STATE.md`) or completed (note in `CHANGELOG.md`).

---

## Sections

1. Prioritization Model
2. Item Format
3. Critical
4. High
5. Medium
6. Low
7. Post-1.0 (Icebox)

---

## 1. Prioritization Model

| Priority | Meaning |
|---|---|
| **Critical** | Blocks the pipeline from functioning or violates an architectural invariant. |
| **High** | Required for a coherent 1.0; a stage or core capability. |
| **Medium** | Important quality/robustness/DX; improves 1.0 but not blocking. |
| **Low** | Nice-to-have polish; safe to defer. |
| **Post-1.0** | Explicitly out of 1.0 scope; reserved extension seams. |

Each item maps to a roadmap sprint where known. Priorities are re-assessed at sprint boundaries.

## 2. Item Format

```
- [BL-XXX] <title> — <one-line description> (sprint: NNN, related: ADR/TD)
```

## 3. Critical

- [BL-001] Repository skeleton & layer packages — create `domain/application/infrastructure/interface/shared` with import-linter contracts. (sprint: 000, related: ADR-006)
- [BL-002] CI quality gates — ruff, mypy/pyright strict, import-linter, pytest wired as blocking. (sprint: 000)
- [BL-003] Domain core — entities, value objects, enums, `DomainError` hierarchy. (sprint: 001, related: ADR-007)
- [BL-004] Workflow engine — `Pipeline`, `PipelineStep`, `StageResult`, checkpoint semantics. (sprint: 002, related: ADR-009)
- [BL-005] Persistence foundation — SQLAlchemy 2 models, mappers, repositories, UoW, Alembic. (sprint: 003, related: ADR-003, ADR-007)
- [BL-006] Configuration tree — Pydantic settings, layered precedence, fail-fast validation, `SecretStr`. (sprint: 004, related: ADR-008)
- [BL-007] Composition root & provider registry — driver→adapter wiring. (sprint: 006/007, related: ADR-005)

## 4. High

- [BL-008] Structured logging + correlation + redaction. (sprint: 005, related: ADR-010)
- [BL-009] CLI commands — `generate`, `resume`, `status`, `render` + presenters. (sprint: 006, related: ADR-001)
- [BL-010] Provider decorator stack — retry/backoff, rate limit, cache. (sprint: 007, related: ADR-005, TD-005)
- [BL-011] Story stage — `StoryGenerator` + `OpenAiStoryGenerator` + `GenerateStory`. (sprint: 008)
- [BL-012] Scene stage — `SceneBuilder` + `LlmSceneBuilder` + scene-splitting service. (sprint: 009)
- [BL-013] Image stage — `ImageProvider` + `ReplicateImageProvider` + per-scene fan-out. (sprint: 010)
- [BL-014] Voice stage — `VoiceProvider` + `ElevenLabsVoiceProvider` + duration capture. (sprint: 011)
- [BL-015] Subtitle stage — `SubtitleProvider` + `WhisperSubtitleProvider` + timing alignment. (sprint: 012)
- [BL-016] Video stage — `VideoComposer` + `FfmpegVideoComposer` → MP4. (sprint: 013, related: TD depends on ffmpeg)
- [BL-017] Full pipeline orchestration + resume/`--force`. (sprint: 014, related: ADR-009)
- [BL-018] Port contract test suites for all providers. (sprint: 017)

## 5. Medium

- [BL-019] Concurrency & rate-limit hardening for per-scene fan-out. (sprint: 015)
- [BL-020] Error handling hardening — retryable/terminal classification, persisted error context, exit codes. (sprint: 016)
- [BL-021] Integration/e2e tests + VCR-style recorded provider responses. (sprint: 018)
- [BL-022] Cost/perf logging — per-stage duration and provider cost. (sprint: 019, related: TD-003)
- [BL-023] Prompt golden-test harness + version rollout via config. (sprint: 008+, related: TD-004, `06_PROMPT_RULES.md`)
- [BL-024] `factory status` rich output (per-scene progress). (sprint: 019)
- [BL-025] Troubleshooting guide expansion in `08_ENVIRONMENT.md`. (sprint: 019)

## 6. Low

- [BL-026] Jittered backoff & circuit breaker for providers. (related: TD-005)
- [BL-027] Configurable output naming/templates for MP4 files.
- [BL-028] `--dry-run` mode that plans stages without calling providers.
- [BL-029] Colored/pretty dev log formatter refinements.
- [BL-030] Shell completion for the `factory` CLI.

## 7. Post-1.0 (Icebox)

- [BL-100] Publish stage — `Publisher` port + platform adapters (e.g. YouTube). (related: `07_WORKFLOW.md` §9)
- [BL-101] HTTP delivery layer (FastAPI) as a sibling interface adapter. (related: ADR-004 — currently a non-goal)
- [BL-102] Web UI over the same use cases. (related: ADR-001 — currently a non-goal)
- [BL-103] Postgres backend behind existing repository ports. (related: ADR-003, TD-002)
- [BL-104] Queue-backed distributed workers + remote asset storage. (related: TD-006)
- [BL-105] Parallel multi-project runs.
- [BL-106] Additional stages — music/score, transitions, multi-voice.
- [BL-107] Automated prompt quality scoring / A/B evaluation. (related: TD-004)

---

### Example — promoting a backlog item into a sprint

> When Sprint 010 starts, `BL-013` (Image stage) moves into active work: it is reflected in `12_PROJECT_STATE.md` under "Current Tasks", its acceptance criteria come from `03_ROADMAP.md` Sprint 010, and on completion the CLI capability is noted in `CHANGELOG.md`.
