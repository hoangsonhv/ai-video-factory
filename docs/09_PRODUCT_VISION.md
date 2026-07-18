# 09 — PRODUCT VISION

**Purpose:** The durable "north star" for AI Video Factory — why it exists, who it serves, what "good" looks like, and the principles that keep product decisions coherent over years. When a scope or priority question arises, this document is the tie-breaker above sprint-level detail.

**Owner:** Technical Lead / Product Owner.

**When to update:** Rarely, and deliberately — when the mission, target user, value proposition, or guiding principles genuinely shift. Sprint-level changes never touch this file.

---

## Sections

1. Vision Statement
2. Problem
3. Target User
4. Value Proposition
5. Product Principles
6. What Success Looks Like (1.0)
7. Long-Term Direction
8. Explicit Non-Goals
9. Guardrails

---

## 1. Vision Statement

**Turn any story idea into a finished video, automatically — with a system whose stable core outlives every AI model it uses.**

AI Video Factory treats video generation as a deterministic, resumable assembly line where each creative capability is a swappable part. The product's durable advantage is not any single model, but an architecture that lets creators ride the AI frontier without rebuilding their pipeline.

## 2. Problem

Creating short-form video from an idea normally means stitching together several tools (writing, image generation, TTS, subtitling, editing) by hand — slow, error-prone, and impossible to reproduce or resume. The tools also churn constantly, so any hand-built pipeline rots. Creators need automation that is reproducible, resumable, and resilient to the underlying AI landscape changing.

## 3. Target User

- **Primary (MVP → 1.0):** technically comfortable creators and operators who work from a terminal, generate videos in batch, and want reproducible, scriptable output.
- **Secondary (post-1.0):** teams who later want a UI/API on top of the same engine (a reserved extension, not a 1.0 goal).

## 4. Value Proposition

- **From idea to MP4 with one command.** No manual tool-hopping.
- **Reproducible and resumable.** Runs checkpoint; failures resume; results are traceable.
- **Model-agnostic.** Swap the story, image, voice, or subtitle provider via config — no rewrites.
- **Built to last.** Clean Architecture isolates volatility; the core is stable for years.

## 5. Product Principles

1. **Stable core, replaceable edge.** The pipeline concept is permanent; providers are disposable.
2. **Reproducibility over cleverness.** Every run's inputs, prompts (versioned), and outputs are traceable.
3. **Resumability is non-negotiable.** No user ever restarts from the idea because of a transient failure.
4. **Config over code.** Behavior changes (provider, concurrency, prompt version) are configuration, not edits.
5. **CLI-first, automation-friendly.** The product is a tool that composes into scripts and pipelines.
6. **Honest failure.** Errors are specific, actionable, and never silently swallowed.
7. **Quality is enforced, not hoped for.** Types, layer boundaries, and tests are machine-checked gates.

## 6. What Success Looks Like (1.0)

- A clean environment can install the CLI and produce a valid MP4 from a single idea.
- All seven stages run, checkpoint, and resume correctly.
- Any provider can be swapped by editing one config value.
- Every port has passing contract tests; every provider is substitutable.
- Operators can fully diagnose a run from structured logs.

## 7. Long-Term Direction

Beyond 1.0, the same engine extends outward without touching the core:
- **Publishing** stage (upload/distribution) as a new port + adapters.
- **More providers** per stage as the AI frontier moves.
- **Scale**: parallel multi-project runs, queue-backed workers.
- **New delivery layers**: an HTTP API and/or UI beside the CLI.
- **Richer media**: music/score, transitions, multi-voice — each a new stage/port.

Each is a bounded addition at the edge (Architecture Document §11), never a rewrite.

## 8. Explicit Non-Goals

Consistent with the ADRs and the Architecture Document, the following are **not** goals for MVP/1.0:
- No Web UI (ADR-001).
- No FastAPI/HTTP API (ADR-004).
- No Docker.
- No non-SQLite database (ADR-003).
- No distributed workers/queue.
- No publishing/distribution in 1.0.

Non-goals are deliberate focus, not missing features — each has a reserved seam for later.

## 9. Guardrails

- Never trade the architecture's inward-dependency rule for short-term speed.
- Never couple the domain to a specific vendor or model.
- Never let a stage become non-resumable.
- Never surface secrets in logs, output, or the database.
- Treat untrusted idea text as content, never as instructions (prompt-injection resistance).

---

### Example — using this document as a tie-breaker

> **Question:** "Should we add a small web dashboard this sprint to make demos nicer?"
> **Resolution:** No. ADR-001 and Principle 5 (CLI-first) plus the explicit non-goal make this out of scope for 1.0. If a UI is genuinely needed later, it attaches as a sibling interface adapter over the same use cases — file it in `11_BACKLOG.md` as post-1.0.
