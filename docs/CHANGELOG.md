# CHANGELOG

**Purpose:** The human-readable, chronological record of notable changes to AI Video Factory across releases. It tells users and contributors what changed, when, and why — distinct from git history (mechanical) and `03_ROADMAP.md` (forward-looking intent).

**Owner:** Technical Lead.

**When to update:** On every release/version bump, and by accumulating entries under `[Unreleased]` as meaningful changes land (new stage, new provider, behavior change, breaking change). At release time, `[Unreleased]` is renamed to the version with a date.

**Format:** Based on [Keep a Changelog](https://keepachangelog.com/); versions follow [Semantic Versioning](https://semver.org/). Change groups: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

---

## [Unreleased]

### Added
- **Sprint 001 — Project Foundation:**
  - `src/` layout with Clean Architecture layer packages under `src/ai_video_factory/` (`domain`, `application`, `infrastructure`, `interface`, `shared`).
  - Configuration: typed `Settings` tree via `pydantic-settings` with `.env` support and fail-fast `ConfigurationError` (env prefix `AIVF_`, `__` nesting).
  - Logging: Rich console + rotating-file handlers, config-driven, idempotent setup.
  - Exceptions: `AppError` hierarchy (`DomainError`, `ApplicationError`, `InfrastructureError` → `ProviderError`/`PersistenceError`/`MediaError`, `ConfigurationError`).
  - CLI: Typer application with `version` and `doctor` commands and a Rich diagnostics presenter; `factory` console script and `python -m ai_video_factory`.
  - Doctor diagnostics: Python version, FFmpeg availability, writable output folder, configuration loading, SQLite connectivity.
  - Tooling: Ruff (lint + format), MyPy (strict), Pytest — configured and passing (30 tests).
  - Project scaffolding: `pyproject.toml` (hatchling, src layout), `.gitignore`, `.env.example`, `README.md`.
- ADR-011 (src layout + foundation tooling: Typer, pydantic-settings, Rich, Ruff-only formatter).
- Architecture Document (canonical) defining Clean Architecture with four inward-pointing layers (Domain, Application, Infrastructure, Interface) plus `shared`.
- Complete project documentation set in `docs/`:
  `00_PROJECT`, `01_AI_CONTEXT`, `03_ROADMAP`, `04_DECISIONS`, `05_CONVENTIONS`, `06_PROMPT_RULES`, `07_WORKFLOW`, `08_ENVIRONMENT`, `09_PRODUCT_VISION`, `10_TECH_DEBT`, `11_BACKLOG`, `12_PROJECT_STATE`, `13_SESSION_HANDOFF`, `CHANGELOG`.
- Architecture Decision Records ADR-001 through ADR-010 (CLI-first, Python 3.13 async, SQLite, no FastAPI, provider abstraction, enforced inward deps, Pydantic v2/entity≠ORM, config-driven fail-fast, resumable checkpoints, structured logging).
- Roadmap Sprint 000 → 020 to v1.0 with per-sprint goals, deliverables, acceptance criteria, and dependencies.
- Initial backlog (Critical/High/Medium/Low/Post-1.0) and technical-debt register (TD-001 … TD-006).

### Changed
- _None._

### Deprecated
- _None._

### Removed
- _None._

### Fixed
- _None._

### Security
- Established the invariant that secrets are handled as `SecretStr`, never logged or persisted, with an active redaction filter (ADR-008, ADR-010).

---

## Release History

_(No versioned releases yet. The first tagged release will be `0.1.0` at the end of Sprint 006 — foundation complete.)_

---

## Planned Version Milestones (from `03_ROADMAP.md`)

| Version | Milestone | Target |
|---|---|---|
| `0.1.0` | Foundation (domain, app, persistence, config, logging, CLI, DI) | End of Sprint 006 |
| `0.2.0` | First stage end-to-end (Story) | End of Sprint 008 |
| `0.5.0` | All six stages exist | End of Sprint 013 |
| `0.9.0` | Full pipeline resumable & observable | End of Sprint 019 |
| `1.0.0` | Release (Idea → MP4 via CLI) | End of Sprint 020 |

> These are planned targets, not releases. Entries move into "Release History" only when a version is actually tagged.

---

### Example release entry (format to follow at first tag)

```
## [0.1.0] — 2026-08-XX

### Added
- Package skeleton with enforced layer boundaries (import-linter).
- Domain core: entities, value objects, enums, DomainError hierarchy.
- Workflow engine: Pipeline, PipelineStep, StageResult with checkpoint semantics.
- SQLite persistence via SQLAlchemy 2 + Alembic; entity⇄ORM mappers; UnitOfWork.
- Config-driven settings tree with fail-fast validation.
- Structured, correlated logging with secret redaction.
- CLI (generate/resume/status/render) + composition root + provider registry.

### Notes
- No AI provider stages yet (first stage arrives in 0.2.0).
```
