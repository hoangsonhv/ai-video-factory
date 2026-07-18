# 01 — AI CONTEXT

**Purpose:** A compact, always-current knowledge snapshot that primes an AI assistant to work productively without re-reading the whole repository. It captures the mental model, invariants, and "gotchas" that are true *right now*. It is refreshed at the end of every sprint so the next session starts warm.

**Owner:** Technical Lead (refreshed collaboratively at sprint close).

**When to update:** At the **end of every sprint**, and immediately whenever a durable invariant changes (a new port, a new provider driver, a renamed layer). This is the *learned context*; `12_PROJECT_STATE.md` is the *factual state*. Keep them consistent.

---

## Sections

1. System Mental Model
2. Hard Invariants (never violate)
3. Layer Map & Import Rules
4. Ports & Current Drivers
5. Key Files To Know
6. Common Tasks → Where They Go
7. Known Pitfalls
8. Sprint Learning Log

---

## 1. System Mental Model

AI Video Factory is a **resumable pipeline state machine**. A `RunPipeline` use case executes ordered stages (`STORY → SCENES → IMAGE → VOICE → SUBTITLE → VIDEO`), persisting a `StageStatus` after each stage in SQLite. Every external capability is a **port** owned by the domain and implemented by an **adapter** in infrastructure, selected by a config `driver`. Wiring happens once in the composition root.

## 2. Hard Invariants (never violate)

- **Dependency direction is inward only.** `domain` imports nothing outward; `application` imports only `domain`; `infrastructure` implements inner ports; `interface` wires everything. Enforced by import-linter in CI.
- **The domain is pure** — no I/O, no SQLAlchemy, no HTTP, no ffmpeg, no vendor SDKs, no `print`.
- **No raw vendor exceptions cross a boundary** — adapters translate to `ProviderError` / `MediaError` / `PersistenceError`.
- **Providers are swapped via config, never code.** Adding a provider = new adapter + registry entry + config `driver`. No edits to existing stages (OCP).
- **Entities ≠ ORM models.** They are separate; mappers translate. Never make an entity a SQLAlchemy model.
- **Every stage is idempotent and checkpointed.** Re-running skips `COMPLETED` stages and resumes from the first incomplete/`FAILED` one.
- **No secrets in logs or the database.** Use `SecretStr`; a redaction filter is active.
- **Async-first.** All I/O is `async`; blocking work (ffmpeg) runs off the event loop.

## 3. Layer Map & Import Rules

| Layer | Package | May import |
|---|---|---|
| Domain | `domain/` | stdlib, Pydantic only |
| Application | `application/` | `domain` |
| Infrastructure | `infrastructure/` | `domain`, `application` |
| Interface | `interface/` | all layers (wiring) |
| Shared | `shared/` | stdlib only |

## 4. Ports & Current Drivers

| Stage | Port | Configured driver | Adapter class |
|---|---|---|---|
| Story | `StoryGenerator` | _pending Sprint 008_ | `OpenAiStoryGenerator` (planned) |
| Scene | `SceneBuilder` | _pending Sprint 009_ | `LlmSceneBuilder` (planned) |
| Image | `ImageProvider` | _pending Sprint 010_ | `ReplicateImageProvider` (planned) |
| Voice | `VoiceProvider` | _pending Sprint 011_ | `ElevenLabsVoiceProvider` (planned) |
| Subtitle | `SubtitleProvider` | _pending Sprint 012_ | `WhisperSubtitleProvider` (planned) |
| Video | `VideoComposer` | _pending Sprint 013_ | `FfmpegVideoComposer` (planned) |
| Persistence | `ProjectRepository`, `UnitOfWork` | `sqlite` | `SqlAlchemyProjectRepository` (planned) |

> Update the "configured driver" column as each stage ships. Keep in sync with `12_PROJECT_STATE.md`.

## 5. Key Files To Know

- `interface/container.py` — composition root; the only file that names concrete adapters.
- `application/workflow/` — pipeline engine, `PipelineStep`, `StageResult`.
- `domain/ports/` — all abstract contracts.
- `infrastructure/config/` — settings tree; provider `driver` selection.
- `infrastructure/providers/**` — adapters, plus decorator adapters for retry/rate-limit/cache.

## 6. Common Tasks → Where They Go

| Task | Location |
|---|---|
| Add a new AI provider | `infrastructure/providers/<stage>/` + registry + config |
| Add a new pipeline stage | new port in `domain/ports/`, use case + step in `application/`, adapter in `infrastructure/` |
| Add a config option | `infrastructure/config/` settings model |
| Change output formatting | `interface/presenters/` |
| Add business rule | `domain/services/` or entity method |

## 7. Known Pitfalls

- Do not read `os.environ` outside the config loader.
- Do not block the event loop with ffmpeg — dispatch via `asyncio.to_thread`/subprocess.
- Do not throw "not supported" from a declared port method — it breaks LSP and contract tests.
- Do not restart a run from scratch on failure — resume from the checkpoint.

## 8. Sprint Learning Log

> Append one entry per sprint. Keep newest at top.

### Sprint 000 — Bootstrap
- Learned: repository, tooling, CI, and this documentation set are the baseline. No runtime code yet.
- New invariants: layer boundaries enforced by import-linter from day one.
- Watch-outs: keep `12_PROJECT_STATE.md` and this file synchronized at every sprint close.

### Example entry (format to follow)
```
### Sprint 010 — Image stage
- Learned: Replicate rate limits at N req/s; RetryingImageProvider decorator handles 429s.
- New invariants: ImageSpec.aspect_ratio must match project AspectRatio; enforced in use case.
- Watch-outs: large image payloads must not be logged at DEBUG (redaction confirmed).
```
