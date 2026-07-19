# 13 — SESSION HANDOFF

**Purpose:** A fill-in template that lets *any* assistant (human or AI) resume the project with **zero context loss**. It captures the exact state at the moment work paused: what was just done, what is in flight, the next concrete action, and every fact needed to continue without re-discovery. It complements `12_PROJECT_STATE.md` (durable state) with *session-local* continuity.

**Owner:** Whoever is ending a working session.

**When to update:** At the **end of every session** (or before a context switch). Overwrite the "Current Handoff" section with the latest; keep a short rolling history below it. Always keep it consistent with `12_PROJECT_STATE.md`.

---

## How To Use

1. Ending a session: fill in "Current Handoff" completely. No blanks, no "TBD".
2. Starting a session: read `12_PROJECT_STATE.md` first, then this file's "Current Handoff".
3. The "Next Action" must be a single, concrete, immediately-executable step.

---

## Current Handoff

**Session date:** 2026-07-19
**Author:** Senior Python Engineer
**Sprint:** 003 — Prompt Engine (delivered)
**Version:** 0.1.0-dev
**Branch:** `feat/sprint003-prompt-engine`

### What was accomplished this session
- Built the Prompt Engine (ADR-013), all in `infrastructure/prompts/`:
  - `PromptLoader` (load + in-memory cache + `PromptNotFoundError`, path-traversal guarded), `PromptRenderer` (Jinja2, `StrictUndefined`), `PromptValidator` (exists + syntax + required variables), `PromptService` façade (`render`/`validate`/`list_prompts`/`load`).
  - Error hierarchy `PromptError → PromptNotFoundError/PromptValidationError/PromptRenderError` (extends `InfrastructureError`).
  - Templates under configurable root `prompts/` (`story/{idea,outline,chapter,scene}.md`, `image/image_prompt.md`) — no prompt text in Python.
  - Config `PromptSettings.root`; CLI `prompt list/show/validate/render`.
- Verified: Ruff, MyPy (strict), Pytest (91, +26) all green; all four `prompt` CLI examples run, including `render story/idea --var topic="Tu tiên" --var style="Trung Quốc"`.
- Fixed a real bug: raw Unicode CLI output crashed on legacy Windows (cp1252) via Rich; raw text now written as UTF-8 bytes.

### Current in-flight work
- None. Prompt engine complete and verified.

### Next Action (do this first)
> Wait for the next Sprint specification from the Lead. Do NOT implement Story/Scene/Image/Video/Workflow — future sprints. Those stages will consume the prompt engine via `PromptService` and an `LLMProvider` from `ProviderFactory`.

### Context needed to continue
- **Prompt engine:** obtain via `PromptService.create(settings.prompts.root)`. Names are `/`-separated without `.md` (e.g. `story/idea`). Rendering is strict: a missing variable → `PromptRenderError`; bad template syntax → `PromptValidationError`.
- **Shipped templates & their required vars:** `story/idea` → {style, topic}; `story/outline` → {idea, style, topic}; `story/chapter` → {chapter, outline, style, topic}; `story/scene` → {chapter, style}; `image/image_prompt` → {scene, style}.
- **Config:** `AIVF_PROMPTS__ROOT` (default `prompts/`).
- **CLI raw text:** goes through `render_text` (UTF-8 bytes) — do not route international prompt content through Rich's console encoder.
- **Tooling:** `uv`; `make lint/format/typecheck/test`. Console script `ai-video-factory`.

### Decisions made this session
- ADR-013 recorded: prompt engine in infrastructure; single **configurable** prompt root (default `prompts/`); Jinja2 with `StrictUndefined`; no prompt text in code. Supersedes the per-adapter location suggestion in `06_PROMPT_RULES.md` §1 (root is configurable, so that layout is still reachable).

### Open questions / risks for next session
- On a truly legacy cp1252 console (not UTF-8), rendered non-ASCII may display as mojibake though it no longer crashes; set the terminal to UTF-8 for correct display. Programmatic use (`PromptService.render`) always returns correct `str`.
- import-linter still not wired as an automated gate.

### Files touched this session
- New source: `infrastructure/prompts/**` (errors, models, loader, renderer, validator, service), `interface/cli/prompt_commands.py`, `interface/presenters/prompt_presenter.py`.
- Modified source: `infrastructure/config/settings.py` (+`PromptSettings`), `interface/cli/app.py` (register `prompt` sub-app).
- Templates: `prompts/story/*.md`, `prompts/image/image_prompt.md`.
- Config/tooling: `pyproject.toml` (+`jinja2`), `.env.example`.
- Tests: `test_prompt_loader/renderer/validator/service/cli.py` (new); `test_settings.py` (updated).
- Docs: `04_DECISIONS.md` (ADR-013), `12_PROJECT_STATE.md`, `13_SESSION_HANDOFF.md`, `CHANGELOG.md`. Architecture doc (`ai-tool.md`) untouched.

### Do NOT do
- Do not add a Web UI, FastAPI, or Docker (ADR-001, ADR-004; non-goals).
- Do not put I/O or vendor code in `domain/`.
- Do not implement Story/Scene/Image/Video/Workflow — those are future sprints.

---

## Handoff History (rolling, newest first)

### 2026-07-19 — Sprint 003 Prompt Engine delivered
- Built loader/renderer(Jinja2)/validator/service + templates under configurable `prompts/`; CLI `prompt list/show/validate/render`; UTF-8-safe output. 91 tests green; ADR-013 recorded.
- Handed off to: next Sprint spec (no future stages implemented).

### 2026-07-18 — Sprint 002 AI Provider Layer delivered
- Built LLM provider abstraction (Protocol, models, error hierarchy, retry, timeout), `GeminiProvider` over `google-genai` (isolated behind a client seam), `ProviderFactory`, provider config, and a `doctor` AI-provider health check. 65 tests green; ADR-012 recorded.
- Handed off to: next Sprint spec (no future stages implemented).

### 2026-07-18 — Sprint 001.5 Foundation Review Fix delivered
- Applied Lead review items: `.gitignore`, `.gitkeep` placeholders, artifact cleanup, `CLAUDE.md`, `.editorconfig`, `Makefile`, pre-commit; verified gates green and app runs.
- No `src/`, test, or architecture changes. Handed off to: next Sprint spec (Domain Core expected; not started).

### 2026-07-18 — Sprint 001 Project Foundation delivered
- Implemented foundation (config, logging, exceptions, CLI, diagnostics) in `src/` layout; 30 tests; all gates green.
- Recorded ADR-011 (layout + tooling). CLI verified (`factory version`, `factory doctor`).
- Handed off to: next Sprint spec (Domain Core is the expected next increment; not yet started).

### 2026-07-18 — Documentation set established
- Delivered Architecture Document + full `docs/` set + ADRs.
- Handed off to: Sprint 000 skeleton & CI work.
- Next action set: create package skeleton + import-linter contracts + CI gates.

---

## Template (copy for each new handoff)

```
## Current Handoff

**Session date:**
**Author:**
**Sprint:**
**Version:**
**Branch:**

### What was accomplished this session
-

### Current in-flight work
-

### Next Action (do this first)
> <one concrete, immediately-executable step>

### Context needed to continue
-

### Decisions made this session
-

### Open questions / risks for next session
-

### Files touched this session
-

### Do NOT do
-
```
