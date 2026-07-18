# 07 — WORKFLOW

**Purpose:** Describe the complete end-to-end pipeline — from a raw idea to a published video — including what each stage consumes and produces, how state is checkpointed, how failures resume, and how concurrency works. This is the operational narrative of the system; the Architecture Document is the structural authority.

**Owner:** Technical Lead.

**When to update:** When a stage is added/reordered, checkpoint/resume semantics change, or the concurrency/fan-out model changes. Must stay consistent with `03_ROADMAP.md` and ADR-009.

---

## Sections

1. Pipeline Overview
2. Stage-by-Stage Contracts
3. State & Checkpointing
4. Resume & Re-run Semantics
5. Concurrency & Fan-out
6. Error Handling in the Pipeline
7. CLI Commands
8. End-to-End Example
9. Publish (Post-1.0)

---

## 1. Pipeline Overview

```
Idea → Story → Scene → Image → Voice → Subtitle → Video → MP4 → (Publish, post-1.0)
```

The pipeline is an explicit, ordered state machine executed by the `RunPipeline` use case. Each stage is a `PipelineStep` wrapping one use case, reading persisted inputs and writing persisted outputs. Stages `STORY` and `SCENES` operate on the project; `IMAGE`, `VOICE`, `SUBTITLE` fan out per scene; `VIDEO` joins all scene assets into one MP4.

```
        project-level              per-scene fan-out            join
   ┌──────────┬──────────┐   ┌────────┬────────┬──────────┐   ┌───────┐
   │  STORY   │  SCENES  │ → │ IMAGE  │ VOICE  │ SUBTITLE │ → │ VIDEO │ → MP4
   └──────────┴──────────┘   └────────┴────────┴──────────┘   └───────┘
```

## 2. Stage-by-Stage Contracts

| Stage | Port | Input | Output (persisted) | Checkpoint key |
|---|---|---|---|---|
| Story | `StoryGenerator` | `Idea`, `LanguageCode` | `Story` (title, body) | `STORY` |
| Scene | `SceneBuilder` | `Story` | ordered `Scene[]` (each with image prompt + narration text) | `SCENES` |
| Image | `ImageProvider` | `Scene` + `AspectRatio`/style | `MediaAsset(kind=IMAGE)` per scene | `IMAGE:<scene_id>` |
| Voice | `VoiceProvider` | narration text + `LanguageCode` + voice id | `MediaAsset(kind=VOICE)` + `Duration` per scene | `VOICE:<scene_id>` |
| Subtitle | `SubtitleProvider` | voice asset / narration + timing | `MediaAsset(kind=SUBTITLE)` (`.srt`/`.vtt`) per scene | `SUBTITLE:<scene_id>` |
| Video | `VideoComposer` | all scene assets | `VideoRender` → MP4 file | `VIDEO` |

Each stage:
1. Loads its inputs from the repository (never from prior in-memory state alone).
2. Calls its port (an injected adapter).
3. Persists outputs + `StageStatus` transactionally via the `UnitOfWork`.
4. Emits correlated start/finish logs and a domain event.

## 3. State & Checkpointing

- The **database is the source of truth** for run progress.
- After each stage (or per-scene unit) completes, its artifact refs and `StageStatus` (`COMPLETED`) are written inside one transaction.
- A `run_id` correlates all logs and events for a single execution.
- Artifacts (images, audio, subtitles, MP4) are stored via `AssetStorage` on the filesystem; the DB holds their references (`FilePath`), not the bytes.

## 4. Resume & Re-run Semantics

- `factory generate` on an existing project inspects persisted state and **skips `COMPLETED` stages**, resuming from the first `PENDING`/`FAILED` one.
- A crash mid-render never forces starting from the idea.
- `factory resume <project_id>` continues an interrupted run.
- `factory generate --force <stage>` deliberately re-runs a specific stage (and its dependents where required).
- Idempotency is mandatory: re-running a completed unit must not duplicate assets — it is a no-op returning the existing `StageResult`.

## 5. Concurrency & Fan-out

- Per-scene stages (`IMAGE`, `VOICE`, `SUBTITLE`) fan out across scenes with **bounded `asyncio` concurrency** from `PipelineSettings` (e.g. `max_concurrent_scenes`), respecting provider rate limits.
- The `VIDEO` stage is a **barrier**: it waits for all required per-scene assets before composing.
- Blocking work (ffmpeg) runs off the event loop via `asyncio.to_thread`/subprocess so fan-out is never stalled.
- A single scene's failure is isolated: it is marked `FAILED` with context; other scenes continue; the run reports partial progress.

## 6. Error Handling in the Pipeline

- Adapters translate vendor/ffmpeg errors to `ProviderError`/`MediaError` with a `retryable` flag.
- Retryable errors (rate limit, transient 5xx) trigger the retry/backoff decorator; terminal errors fail the unit immediately.
- A failed stage/unit persists structured error context and stops the affected branch; completed work stays intact and resumable.
- The CLI boundary maps unhandled `AppError` → clean message + non-zero exit; unexpected exceptions → logged traceback + generic message (full trace only with `--verbose`).

## 7. CLI Commands

| Command | Purpose |
|---|---|
| `factory generate --idea "..." [--lang xx] [--force <stage>]` | Start/continue a full pipeline run |
| `factory resume <project_id>` | Resume an interrupted run |
| `factory status [<project_id>]` | Show run/stage/scene status |
| `factory render <project_id>` | Run only the `VIDEO` stage from existing assets |

## 8. End-to-End Example

```
$ factory generate --idea "A lighthouse keeper who befriends a storm" --lang en

[run_id=r-8f2a] INFO  stage=STORY    started
[run_id=r-8f2a] INFO  stage=STORY    completed (1 story, 1.2s)
[run_id=r-8f2a] INFO  stage=SCENES   completed (5 scenes, 2.0s)
[run_id=r-8f2a] INFO  stage=IMAGE    scene=1..5 fan-out (max_concurrent=3)
[run_id=r-8f2a] WARN  stage=IMAGE    scene=3 retry (provider 429, retryable)
[run_id=r-8f2a] INFO  stage=IMAGE    completed (5 assets, 18.4s)
[run_id=r-8f2a] INFO  stage=VOICE    completed (5 assets, 22.1s)
[run_id=r-8f2a] INFO  stage=SUBTITLE completed (5 cues sets, 6.7s)
[run_id=r-8f2a] INFO  stage=VIDEO    composing (ffmpeg)
[run_id=r-8f2a] INFO  stage=VIDEO    completed → output/lighthouse.mp4 (12.9s)

Done. project_id=p-101  output=output/lighthouse.mp4
```

Resume after an interrupted run:
```
$ factory resume p-101
[run_id=r-9c1b] INFO  stage=STORY    skipped (already COMPLETED)
[run_id=r-9c1b] INFO  stage=SCENES   skipped (already COMPLETED)
[run_id=r-9c1b] INFO  stage=IMAGE    scene=3 resuming (was FAILED)
...
```

## 9. Publish (Post-1.0)

Publishing (upload/distribution to a target platform) is a **post-1.0** stage, not part of 1.0. When added, it follows the same pattern: a `Publisher` port in the domain, a `PublishVideo` use case + `PipelineStep`, and platform adapters (e.g. `YouTubePublisher`) selected by config `driver`. It attaches at the end of the pipeline (`VIDEO → PUBLISH`) with its own checkpoint (`PUBLISH`), inheriting resume, logging, and error-translation behavior with no changes to existing stages (Architecture Document §11). Tracked in `11_BACKLOG.md`.
