# 05 — CONVENTIONS (Coding Standards)

**Purpose:** The enforceable rulebook for how code is written in this repository. It makes the codebase uniform, readable, and machine-checkable so it stays maintainable for years. Where possible, rules are enforced by tooling (ruff, mypy/pyright, import-linter) rather than by reviewer memory.

**Owner:** Technical Lead.

**When to update:** When a convention is added, tightened, or relaxed. Changes must remain consistent with the Architecture Document and relevant ADRs. Tooling config changes accompany any rule change.

---

## Sections

1. General Principles
2. Naming Conventions
3. Typing
4. Logging
5. Error / Exception Handling
6. Testing
7. Folder Naming
8. File Naming
9. Exception Naming
10. Prompt Naming
11. Git Commit Naming
12. Branch Naming
13. Enforcement (Tooling)

---

## 1. General Principles

- **SOLID, structurally.** One class = one reason to change. New behavior is added (new adapter/stage), not patched into existing classes.
- **Async-first.** All I/O is `async`. Never block the event loop; dispatch blocking work (ffmpeg) via `asyncio.to_thread`/subprocess.
- **Immutability by default.** Value objects are `frozen`. Entities mutate only via intention-revealing methods.
- **No global mutable state.** No module-level sessions/clients/singletons. Everything is constructed in the composition root and injected.
- **Pure domain.** No I/O, frameworks, vendor SDKs, or `print` in `domain/`.
- **Small functions, pushed side effects.** Pure logic inward; effects at the edges.

## 2. Naming Conventions

| Element | Rule | Example |
|---|---|---|
| Package/module | `snake_case`; singular concept, plural collections | `domain.entities.scene`, `use_cases` |
| Class | `PascalCase` | `VideoRender` |
| Function/variable | `snake_case` | `build_scenes` |
| Constant | `UPPER_SNAKE_CASE` | `DEFAULT_ASPECT_RATIO` |
| Port (interface) | role/capability, no `I` prefix | `ImageProvider`, `ProjectRepository` |
| Adapter (impl) | `<Vendor/Tech><Role>` | `FfmpegVideoComposer`, `ElevenLabsVoiceProvider` |
| Use case | verb phrase; method `execute` | `GenerateStory`, `ComposeVideo` |
| DTO | `<Action>Command` / `<Action>Result` | `GenerateStoryCommand` |
| Value object | noun concept | `Duration`, `SubtitleCue` |
| Enum | singular noun; members `UPPER_SNAKE` | `StageStatus.COMPLETED` |
| Identifier types | `NewType` per id | `ProjectId`, `SceneId` |
| Boolean | `is_`/`has_`/`should_` prefix | `is_completed`, `has_audio` |

Adapter names must reveal exactly what they wrap: `SqlAlchemyProjectRepository`, `OpenAiStoryGenerator`, `ReplicateImageProvider`, `WhisperSubtitleProvider`.

## 3. Typing

- Full type hints on **every** function signature. `mypy --strict` (and/or pyright strict) is a CI gate.
- No untyped `dict` across boundaries — use Pydantic models or dataclasses.
- Use `NewType` for identifiers to prevent mixing (`ProjectId` ≠ `SceneId`).
- Prefer precise types: `Sequence`/`Mapping` for read-only inputs, concrete types for outputs.
- `Any` is banned except at a documented vendor-SDK boundary, and must be narrowed immediately.
- Async functions declare `-> Awaitable`-consistent return types via `async def`; no untyped coroutines.

## 4. Logging

- Use module loggers: `logging.getLogger(__name__)`. **No `print`** except in `interface/presenters/`.
- Every log line within a run carries correlation fields (`run_id`, `project_id`, `stage`, and `scene_id`/`provider` where relevant) via `contextvars`.
- Levels: `DEBUG` (timing, payload sizes, redacted prompts), `INFO` (lifecycle: stage start/finish, artifact written), `WARNING` (retryable failures, fallbacks, skips), `ERROR` (stage/terminal failures), `CRITICAL` (unrecoverable/config aborts).
- Never log secrets. `SecretStr` + redaction filter are mandatory.
- Logs are for operators; user-facing output goes through presenters. Keep the channels separate.

## 5. Error / Exception Handling

- Hierarchy rooted at `AppError`: `DomainError`, `ApplicationError`, `InfrastructureError` (→ `ProviderError`, `PersistenceError`, `MediaError`), `ConfigurationError`.
- **Translate at boundaries.** Adapters catch vendor exceptions and re-raise as domain-meaningful errors; raw vendor exceptions never cross inward.
- Exceptions carry structured context (stage, ids, provider, `retryable` flag).
- No bare `except:` / `except Exception: pass`. Every catch handles, translates, or re-raises with context.
- Expected outcomes (skipped/already-done) are represented as `StageResult` data, not exceptions.
- Fail fast on config at startup; never mid-render.

## 6. Testing

- `pytest` + `pytest-asyncio`; async tests are first-class.
- Test pyramid: domain unit (largest) → application (fakes) → port contract → infrastructure integration → e2e smoke.
- Application tests use in-memory fakes of ports; no network, DB, or ffmpeg.
- Every port implementation must pass the shared **contract test suite** for that port (LSP guarantee).
- No test hits a paid API or the network by default; live tests are `@pytest.mark`-gated and opt-in.
- Property-based tests (Hypothesis) for value objects and timing/alignment logic.
- Coverage gates on `domain` + `application`.
- Test naming: `test_<unit>_<condition>_<expected_outcome>`.

## 7. Folder Naming

- Lowercase `snake_case`, no spaces or hyphens.
- Collection packages plural (`use_cases`, `providers`, `repositories`); concept modules singular (`scene.py`).
- Provider folders grouped by stage: `infrastructure/providers/{story,image,voice,subtitle}`.
- Test folders mirror source: `tests/{domain,application,infrastructure,interface,contract,e2e}`.

## 8. File Naming

- `snake_case.py`, one primary concept per file, filename matches its main class (`ffmpeg_video_composer.py` → `FfmpegVideoComposer`).
- Errors modules named `errors.py` per layer.
- Test files: `test_<module>.py`; contract suites: `test_<port>_contract.py`.
- Migrations follow Alembic's timestamped revision naming.

## 9. Exception Naming

- Suffix `Error`, `PascalCase`, specific: `InvalidSceneError`, `EmptyStoryError`, `StageFailedError`, `PipelineAbortedError`, `ImageProviderError`, `VoiceProviderError`, `PersistenceError`, `MediaError`, `ConfigurationError`.
- Base classes per layer: `DomainError`, `ApplicationError`, `InfrastructureError`.
- Never name an exception generically (`Error1`, `MyException`) or stringly-type failures.

## 10. Prompt Naming

- Prompt templates live in `infrastructure/providers/<stage>/prompts/` as versioned files: `<purpose>.v<major>.md` (e.g. `story_from_idea.v1.md`, `scene_split.v2.md`).
- Template variables use `snake_case` placeholders.
- A prompt's version is bumped on any wording change that can alter output; the active version is referenced in config. See `06_PROMPT_RULES.md`.

## 11. Git Commit Naming

Conventional Commits:

```
<type>(<scope>): <subject>
```

- **type:** `feat | fix | refactor | test | docs | chore | perf | build | ci`.
- **scope:** layer or stage — `domain | application | infra | cli | image | voice | subtitle | video | story | scene | config | workflow | docs`.
- **subject:** imperative, ≤ 72 chars, no trailing period.

Examples:
```
feat(image): add ReplicateImageProvider adapter and registry entry
fix(workflow): resume from first FAILED stage instead of restarting
docs(decisions): add ADR-011 for prompt versioning
test(voice): add VoiceProvider contract suite
```

## 12. Branch Naming

```
<type>/<sprint>-<short-description>
```
- **type:** `feat | fix | chore | docs | refactor | test`.
- **sprint:** `sprintNNN` (e.g. `sprint010`).
- Example: `feat/sprint010-image-stage`, `fix/sprint016-error-translation`, `docs/sprint000-doc-set`.
- `main` is protected; work merges via reviewed PRs with green CI.

## 13. Enforcement (Tooling)

| Rule area | Tool | Gate |
|---|---|---|
| Format & lint | ruff | CI blocking |
| Typing | mypy / pyright (strict) | CI blocking |
| Layer boundaries | import-linter | CI blocking |
| Tests & coverage | pytest + coverage | CI blocking |
| Commit format | commit lint (local hook + CI) | CI warning→blocking |

Any convention that *can* be automated *must* be automated. Manual conventions are documented here and checked in review.
