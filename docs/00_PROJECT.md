# 00 — PROJECT

**Purpose:** The top-level entry point to the project. A newcomer (human or AI) reads this first to understand *what* AI Video Factory is, *why* it exists, *what* it does, and *where* to go next. It is the map of the documentation set.

**Owner:** Technical Lead.

**When to update:** When the project's high-level identity changes — mission, MVP scope boundary, supported stages, the documentation index, or the tech stack summary. Not updated for routine sprint work (that lives in `12_PROJECT_STATE.md`).

---

## Sections

1. Mission
2. What It Does (Pipeline)
3. Scope & Non-Goals
4. Tech Stack Summary
5. Architecture Summary
6. Repository Layout
7. Documentation Index
8. How To Get Started
9. Glossary

---

## 1. Mission

AI Video Factory turns a single **story idea** into a finished **MP4 video**, fully automatically, through a deterministic, resumable pipeline. Each stage is a replaceable transformation; each AI capability is hidden behind a stable contract so models and vendors can change without rewriting the system.

## 2. What It Does (Pipeline)

```
Idea → Story → Scene → Image → Voice → Subtitle → Video → MP4
```

The MVP produces a rendered MP4 with per-scene imagery, synthesized narration, and burned/attached subtitles. Publishing (upload/distribution) is a defined post‑1.0 extension and is documented in `07_WORKFLOW.md`, but is **not** part of the 1.0 deliverable.

## 3. Scope & Non-Goals

**In scope (MVP → 1.0):** CLI-driven generation, all seven pipeline stages, SQLite persistence with checkpoint/resume, config-driven provider selection, structured logging, full test suite.

**Non-goals (deferred, seams reserved):**
- No Web UI.
- No FastAPI / HTTP API.
- No Docker (yet).
- No distributed queue / remote workers.
- No database other than SQLite.
- No publishing/distribution in 1.0.

These deferrals are ADR-backed (`04_DECISIONS.md`) and each has a reserved extension seam per the Architecture Document §11.

## 4. Tech Stack Summary

| Concern | Choice |
|---|---|
| Language | Python 3.13 |
| Concurrency | async-first (`asyncio`) |
| Validation / models | Pydantic v2 |
| ORM | SQLAlchemy 2 |
| Database | SQLite |
| Migrations | Alembic |
| Media rendering | ffmpeg (subprocess adapter) |
| CLI | CLI-first (no Web UI) |
| Lint/format | ruff |
| Type checking | mypy / pyright (strict) |
| Layer enforcement | import-linter |
| Tests | pytest, pytest-asyncio, Hypothesis |

## 5. Architecture Summary

Clean Architecture, four inward-pointing layers: **Domain → Application → Infrastructure → Interface**, with a `shared` dependency-free utility package. Dependencies point inward only; volatile concerns (AI providers, DB, ffmpeg) sit behind ports owned by the domain and are wired once at the composition root. See the Architecture Document (canonical) and `04_DECISIONS.md`.

Current Architecture Version: **1.0** (see `12_PROJECT_STATE.md`).

## 6. Repository Layout

```
ai_video_factory/
├── domain/          # entities, value_objects, enums, services, ports, errors
├── application/     # use_cases, workflow, ports, dto, errors
├── infrastructure/  # providers, persistence, media, config, logging, clients
├── interface/       # cli, presenters, container (composition root)
├── shared/          # framework-free utilities
└── main.py
docs/                # this documentation set
tests/               # unit, application, contract, integration, e2e
```

## 7. Documentation Index

| File | Contents |
|---|---|
| `00_PROJECT.md` | This file — project map & entry point |
| `01_AI_CONTEXT.md` | Per-sprint knowledge snapshot for AI assistants |
| `03_ROADMAP.md` | Sprint 000 → 020 plan to v1.0 |
| `04_DECISIONS.md` | Architecture Decision Records (ADRs) |
| `05_CONVENTIONS.md` | Coding standards & naming conventions |
| `06_PROMPT_RULES.md` | Prompt engineering guidelines |
| `07_WORKFLOW.md` | End-to-end pipeline workflow |
| `08_ENVIRONMENT.md` | Development environment setup |
| `09_PRODUCT_VISION.md` | Product vision & principles |
| `10_TECH_DEBT.md` | Technical debt register |
| `11_BACKLOG.md` | Prioritized backlog |
| `12_PROJECT_STATE.md` | **Single source of truth — read first** |
| `13_SESSION_HANDOFF.md` | Zero-context-loss handoff template |
| `CHANGELOG.md` | Human-readable release history |

> Note: `02` is intentionally unused; the numbering is reserved for a future document without renumbering the set.

## 8. How To Get Started

1. Read `12_PROJECT_STATE.md` (current state — always first).
2. Read this file (`00_PROJECT.md`) and the Architecture Document.
3. Set up your environment via `08_ENVIRONMENT.md`.
4. Read `05_CONVENTIONS.md` before writing any code.
5. Pick work from `11_BACKLOG.md` aligned with the current sprint in `03_ROADMAP.md`.

## 9. Glossary

- **Stage** — one transformation in the pipeline (Story, Scene, Image, Voice, Subtitle, Video).
- **Port** — an abstract contract owned by the domain (e.g. `ImageProvider`).
- **Adapter** — a concrete implementation of a port living in infrastructure (e.g. `FfmpegVideoComposer`).
- **Driver** — the config key selecting which adapter implements a stage's port.
- **Composition Root** — `interface/container.py`, the single place concretes are wired to ports.
- **Run** — one execution of the pipeline for a project, identified by a `run_id`.
- **Checkpoint** — persisted stage status enabling resume.

### Example — orienting a new AI assistant

> "You are joining AI Video Factory. Read `docs/12_PROJECT_STATE.md`, then this file. The system is a CLI pipeline (Idea→…→MP4) built on Clean Architecture. Do not add a Web UI, FastAPI, or Docker — those are non-goals (see ADR-001, ADR-004). Providers are swapped via config `driver` keys, never code changes."
