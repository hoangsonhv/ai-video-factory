# 12 — PROJECT STATE (Single Source of Truth)

> **⚠ READ THIS FILE FIRST before continuing any development.**
> This is the authoritative, always-current snapshot of the project. Where this file and any other document disagree about *current state*, this file wins. Where this file and the Architecture Document disagree about *structure*, the Architecture Document wins — and this file must be corrected.

**Purpose:** The one place that answers "where are we right now?" — version, sprint, what's done, what's in progress, what's next, what's blocked, and the live configuration of providers and modules. Every session begins here.

**Owner:** Technical Lead (updated by whoever advances the work).

**When to update:** At the **start and end of every working session** and at every sprint boundary. Keep it terse and factual. Keep `01_AI_CONTEXT.md` consistent with it.

**Last updated:** 2026-07-20

> **Sprint numbering note:** The executing plan from the Lead labels the foundation work **"Sprint 001 — Project Foundation"** (bootstrap + config + logging + CLI + exceptions + tests + tooling). This differs from the roadmap's Sprint 001 ("Domain Core"); the foundation was implemented per the Lead's explicit spec. Roadmap re-alignment, if desired, is the Lead's call.

---

## 1. Current Version

`0.1.0-dev` (foundation delivered; targeting `0.1.0` tag at end of the foundation milestone)

## 2. Current Sprint

**Sprint 026 (second spec) - Cinematic Shot Planner - DELIVERED** (ADR-040; `storyboard.json` -> `shot_plan.json` + `shot_statistics.json`; supersedes ADR-039)

> Two specs arrived under the number 026; this one re-specifies the same problem more completely and **supersedes** the Cinematic Director as the producer of `shot_image_prompts.json` (the `cinema` command still works and is still tested - nothing was removed). Every shot gets all sixteen planned fields. Coverage follows what each scene is doing, and the **film is validated as a distribution** - close <=20%, medium 20-35%, wide/full body >=40%, establishing >=5% - re-planning automatically until it balances. Every frame must state a foreground, midground or background or the shot is **rejected**. `PromptComposer` rewritten to the specified 11-section order, with portrait language stripped from source text and refused in the negatives. On the real film: close **3.3%**, wide/full body **56.7%**, body visibility 19 full / 10 waist / 1 head. No provider, video or compose change.

**Sprint 026 (first spec) - Cinematic Director - DELIVERED, superseded** (ADR-039; `storyboard.json` -> `cinematic_direction.json`; the shot list is directed, not described)

> `SceneDirector` decides what each scene is for (purpose, emotion, conflict, story beat); `ShotDirector` decides how each shot is filmed (type, angle, lens, composition, blocking, lighting, action, motion). Deterministic - the same storyboard always yields the same coverage. **85mm can no longer be a default**: lenses come from a table keyed by shot size and alternate within it (real film: 24mm x12, 35mm x7, 50mm x5, 85mm x3, 135mm x3). Static actions are replaced with active ones. `PromptComposer` rewritten to the director's order, with `direction` optional so existing callers are unaffected. No provider, video or compose change.

**Sprint 025C - Character Memory Engine - DELIVERED** (ADR-038; `character_memory.json` + `appearance_scores.json`; every prompt restates a frozen identity)

> Each character's canonical look is derived once then frozen - reloaded on later runs, never overwritten. The first image that exists for a character becomes its reference and is never re-pointed. `AppearanceValidator` scores eight attributes and rebuilds any prompt below the threshold. Deterministic and offline; no provider, video or compose change.

**Sprint 025B - Visual Continuity Engine - DELIVERED** (ADR-037; `storyboard.json` + bibles -> continuity-aware prompts, contexts and scores)

> Every image prompt is composed from the character bible, world bible, visual context and the shots either side of it - never from the current shot alone. A scorer grades five continuity dimensions and recomposes anything below 90 at a higher level of explicitness. Deterministic and offline; `image_prompts.json`, the providers, the video stage and compose are all untouched.

**Sprint 025 - AI Video Generation - DELIVERED** (ADR-036; `storyboard.json` -> `output/video_clips/shot_NNN.mp4` + manifest)

> Shots merged into 4-8s clips within scene boundaries (timeline preserved exactly: 30 shots -> 20 clips, 90.0s). Provider contract is now `generate(request, references)` with character / scene / previous-clip stills for consistency. Portrait 1080x1920 from `VideoSettings`, so compose is unaffected. `--resume` reuses clips already rendered. Director, storyboard and compose untouched.

**Sprint 024 - Storyboard Builder + OpenRouter Director Provider - DELIVERED** (ADR-034, ADR-035)

> Two specs arrived under the same sprint number and both were delivered. **OpenRouter** (ADR-034): the director runs on `deepseek/deepseek-chat-v3` via a new provider satisfying the existing `LLMProvider` protocol; `AIVF_DIRECTOR_PROVIDER` selects it independently of the story pipeline. **Storyboard** (ADR-035): `movie_directed.json` -> `storyboard.json`, every shot flattened onto a timeline with absolute speech windows, mapped subtitles and audio slices. Both are additive; compose, image generation and TTS untouched.

**Sprint 023 — Batch Director + Shot Planner — DELIVERED** (ADR-033; scenes are broken into shots; still one LLM call per movie)

> `DirectedScene.shots` replaces the scene-level `director`/`director_prompt` block. 3-8 shots per scene at 2-5s each (capped by what the scene's length allows), ids renumbered, durations clamped, each shot's `video_prompt` composed from the character library + its own camera/motion fields. One request plans the whole movie; retries re-ask that request.

**Sprint 022B — Director Single-Request Refactor — DELIVERED** (ADR-032; one Gemini call plans the whole movie; supersedes ADR-031's per-scene planning)

> The prompt carries all scenes + character library + locations; the model answers with one `{"scenes":[...]}` block mapped back by `scene_id`. Retries re-ask that **one** request (transient: backoff+jitter; unparseable: up to 3 attempts) — never per scene. Partial output, `--resume` and the report are retained; `--resume` re-asks only the unplanned scenes, still in one request.

**Sprint 022A — Director Provider Resilience — DELIVERED** (ADR-031; per-scene retry with jitter, failure isolation, partial output, `--resume`)

> Root cause fixed: the Gemini client caught only the SDK's `APIError`, so connection/read timeouts escaped untranslated and unretried (502/503/504 were already handled). The director now plans **one scene per request** with five retries (1s/2s/4s/8s/16s ±20% jitter); a scene that still fails is left unplanned and the run continues. Partial output → `movie_directed.partial.json`; `--resume` re-plans only the failures. **Costs ~10× the requests** of the old bulk call.

**Sprint 022 — AI Director — DELIVERED** (ADR-030; new `director` CLI → `output/movie_directed.json`; providers / image generation / compose untouched)

> Movie → **Director** → Directed Movie. `DirectorService` plans every shot via the LLM (16 fields per scene) and composes a `director_prompt` aimed at **AI video models** — identity from the character library, then shot, camera motion, subject/hand/pose/expression motion, hair/cloth/environment motion, lighting, mood, setting, transitions, and a temporal-coherence directive. Original scene fields preserved verbatim. Verified live (10 scenes, all 16 fields, 5 distinct shot types).

**Sprint 021A — Cost Guard — DELIVERED** (ADR-029; `video generate` gains `--dry-run`, `--limit N` and a confirmation prompt for paid providers; manifest now records `estimated_cost` + `actual_cost`)

> Spending now requires an interactive "y" or an explicit `--yes`; the prompt defaults to No and a non-interactive stream declines. `--dry-run` previews provider/model/scenes/jobs/duration/cost without credentials and submits nothing. `mock` never prompts.

**Sprint 021 — Kling Video Provider — DELIVERED** (first real AI video driver behind the Sprint 020 contract; ADR-028; compose / TTS / image generation untouched)

> `infrastructure/video/providers/kling/`: `RealKlingClient` (only HTTP module, behind a seam) + `KlingVideoProvider` implementing `VideoProvider` — image-to-video with `submit_job` / `poll_job` / `download_result` / `cancel_job`, exponential-backoff retry, poll timeout + cancellation, and clean error translation. `video generate --movie` writes `output/video_clips/scene_NNN.mp4` + `manifest.json`. **`mock` stays the default driver** (Kling needs a paid key). Live Kling API unverified — no credentials; verified against a local stub HTTP server.

## 3. Completed

- **Sprint 025C - Character Memory Engine - done:**
  - New domain VOs `domain/value_objects/character_memory.py`: `CharacterMemory` (every documented field + gender/age/style), `AppearanceScore` (+ documents), `appearance_hash` drift detection.
  - New `infrastructure/memory/`: `builder.py` (derive the canon, merge without overwriting, adopt the first image as reference), `validator.py` (`AppearanceValidator`, 8 attributes), `enricher.py` (reference + appearance summary + previous appearance, escalating explicitness, provider-aware reference handling), `engine.py`, `reader.py`.
  - New CLI `character memory --storyboard ... [--prompts --images --threshold]` -> `character_memory.json`, `appearance_scores.json`, and rewritten `shot_image_prompts.json`.
  - **The canon is frozen**: a remembered value is never overwritten; only gaps are filled and newcomers added. An adopted reference is never replaced.
  - **Unrecorded attributes score 0**, marked `(not remembered)` - the same honesty rule as ADR-037.
  - Tests (47 new): canon derivation, weapon separation, drift detection, merge-without-overwrite, reference adoption and permanence, provider capability, enrichment escalation, validation floor and ceiling, engine determinism, CLI. **899 pass.**
  - Live: average appearance score **97** across 30 prompts; `diep_pham` adopted `001.png`; the standing deduction is `weapon (not remembered)`.

- **Sprint 025B - Visual Continuity Engine - done:**
  - New domain VOs `domain/value_objects/continuity.py`: `CharacterBible`, `WorldBible`, `VisualContext`, `PromptScore` (+ documents).
  - New `infrastructure/continuity/`: `bibles.py` (derive both bibles from the character library and movie), `context.py` (previous / current / next + the six continuity axes), `prompt_composer.py` (three escalating levels), `scorer.py` (five dimensions), `engine.py`, `reader.py`.
  - New CLI `continuity --storyboard ... [--movie --library --threshold]` -> `character_bible.json`, `world_bible.json`, `visual_context.json`, `shot_image_prompts.json`, `prompt_scores.json`.
  - **Hand-edited bibles survive a rerun** - only what is missing is derived.
  - **Continuity is asserted only within a scene**, never across a cut.
  - Tests (47 new): bible derivation, context neighbours and scene boundaries, every required prompt section, escalation genuinely rewriting the text, non-tautological scoring, engine determinism, CLI. **852 pass.**
  - Live on the real 30-shot storyboard: **average score 93**, one shot at 83 reported with its missing elements named. `image_prompts.json` verified untouched (still 6 entries).

- **Sprint 025 - AI Video Generation - done:**
  - New `clip_planner.py`: groups consecutive shots **within one scene** into 4-8s clips; timeline preserved exactly (no shot dropped, stretched or reordered).
  - New `storyboard_source.py`: storyboard -> clip requests + the references each clip may condition on (character stills, scene still, previous clip).
  - **Provider contract `generate(request, references)`** with a new `ClipReferences` model; mock and Kling both updated. Requests now carry `clip_id`, `shot_ids`, `width`, `height`.
  - Clips named `shot_NNN.mp4` per spec; manifest records `clip_id` + `shot_ids` so the merge is auditable.
  - CLI `video generate --storyboard ...` plus `--resume`; `--movie` keeps the Sprint 021 route working.
  - Tests (48 new): provider contract with references, clip planning, resume, retry, manifest, CLI. 805 pass.
  - **Two gaps reported, not hidden**: 10 of 20 real clips are 3s (a 9s scene of 3s shots cannot split evenly - fix is longer shots from `director`), and character reference images are always empty because `CharacterProfile.reference_image` has been `None` since Sprint 019.

- **Sprint 024 - Storyboard Builder - done:**
  - New domain VOs `domain/value_objects/storyboard.py`: `StoryboardShot` (the 20 specified fields), `AudioSegment`, `Storyboard`.
  - New `infrastructure/storyboard/`: pure `builder.py` (timeline + narration mapping + still-frame prompt), `narration.py` (own `.srt` parser keeping the text), `reader.py`, `errors.py`. **Offline** - no provider call.
  - Shots laid end to end give absolute `speech_start`/`speech_end`; narration mapped **by overlap**; `audio_segment` clipped to the real track length; **durations never rewritten** (drift reported instead).
  - CLI `storyboard --movie output/movie_directed.json [--subtitles --library]` -> `output/storyboard.json`.
  - Tests (50 new): timeline contiguity, duration validation, narration mapping, drift, prompts, schema, CLI.
  - Live: 30 shots / 10 scenes / 90.0s from the real directed movie. **Surfaced a data defect** - `narration.srt` is timed to 109.5s but the audio is 66.7s, so the existing subtitles are mistimed; the CLI now warns.

- **Sprint 024 - OpenRouter Director Provider - done:**
  - New `infrastructure/providers/openrouter/`: `RealOpenRouterClient` (only HTTP module, behind a seam) + `OpenRouterProvider` satisfying the **existing** `LLMProvider` protocol.
  - `ProviderFactory.create_director()` / `director_model()` select the director's provider from `AIVF_DIRECTOR_PROVIDER`, independently of the story pipeline's own.
  - Config uses the **flat** names specified (`AIVF_DIRECTOR_PROVIDER`, `AIVF_OPENROUTER_API_KEY`, `AIVF_OPENROUTER_MODEL`), re-exposed to code as a typed `Settings.openrouter`. Default model `deepseek/deepseek-chat-v3`.
  - `count_tokens()` estimates (~4 chars/token) - no counting endpoint exists. Tests (53 new), all HTTP mocked. **Live OpenRouter API unverified** - no credentials.

- **Sprint 023 — Batch Director + Shot Planner — done:**
  - **Domain replaced**: `Shot` (the 13 specified fields) + `DirectedScene.shots`; `DirectorNotes`/`director_prompt` removed rather than left as dead data. `movie_directed.json` still validates as a plain `Movie`.
  - **One LLM request per movie** (ADR-032 retained): prompt carries every scene, the cast and the locations; answer is one `{"scenes":[{"scene_id":n,"shots":[...]}]}` document. Invalid JSON re-asks the whole request (3 attempts); transient failures back off with jitter. Never per scene.
  - **Shot arithmetic** (`shot_planner.py`): `target_shot_count()` prefers the 3-8 band but never exceeds `duration // 2`, so a 5s scene gets 2 shots instead of an impossible 3.
  - **Parser repairs deterministically**: renumber ids 1..N, clamp durations to 2-5s (missing → even split), trim beyond 8. Structural failures reported.
  - **Prompt composition**: identity from the character library, camera/motion from the shot, the model's line folded in as the beat, plus the temporal-coherence directive and library negatives.
  - **Leak fixed**: the injected master prompt inside each scene's `video_prompt` is stripped before the request is built (found during verification — the cast section alone was not enough).
  - Tests rewritten for shots (models, planner arithmetic, batch parsing, prompt composition, service, CLI, resume). **667 pass.**
  - Verified on the real 10-scene movie with a stubbed provider: **1 request**, 30 shots, all durations in range, ids renumbered, identity in every prompt, appearance absent from the request. **Live API unverified — the Gemini key is quota-exhausted.**

- **Sprint 022B — Director Single-Request Refactor — done:**
  - **One provider request per run.** Prompt carries every scene, the character library (ids + voice notes only — appearance stays out, per ADR-026) and the locations; the answer is one `{"scenes":[...]}` block mapped back by `scene_id`.
  - **Retry at the request level, never per scene**: transient failures use the shared `RetryPolicy` (5 retries, 1s/2s/4s/8s/16s ±20% jitter); an unparseable answer re-asks the whole question up to `PARSE_ATTEMPTS` (3).
  - A scene the answer omits is left unplanned (empty `director_prompt`) → partial file → `--resume` re-asks only those scenes, still in one request.
  - Retained from 022A: Gemini transport-error translation, opt-in `RetryPolicy` jitter/`on_retry`, partial output, `--resume`, `DirectionReport`.
  - Tests rewritten for single-request semantics (30 in `test_director_resilience.py`, CLI resume/partial suite updated): exactly-one-call, prompt contents, transient retry, invalid-JSON re-ask, mapping, omission, resume. **659 pass.**
  - **Two issues found during verification, both open**: the `google-genai` SDK retries internally (~4 HTTP POSTs per logical call, so our 6 attempts became 24 requests), and `RetryPolicy` caps the server's `retry_after` hint at `max_delay` (Gemini asked for 51s, we waited 16.5s — guaranteeing another 429).

- **Sprint 022A — Director Provider Resilience — done:**
  - **Root cause**: `RealGeminiClient` caught only `genai_errors.APIError`, which exists only once an HTTP response arrives — connection timeouts, read timeouts and dropped sockets escaped as raw `httpx` exceptions, unretried and untranslated. `map_transport_error()` now converts them at all three SDK call sites. 502/503/504 were already mapped and retried correctly.
  - **Per-scene planning**: one LLM request per scene (previously one for the whole movie), so a transient failure costs one scene instead of the run. Each request carries the previous scene's plan to preserve rhythm.
  - **Retry**: 5 retries/scene, backoff 1s/2s/4s/8s/16s with **±20% jitter**, on 429/500/502/503/504 + connection/read timeouts; terminal errors not retried. `RetryPolicy` gained **opt-in** `jitter` and `on_retry` (defaults unchanged → no other provider's timing moved).
  - **Isolation**: a failed scene keeps empty `director`/`director_prompt` (deliberately *no* fallback notes — emptiness is the resume marker) and the run continues.
  - **Partial output**: some successes → `movie_directed.partial.json` + exit 1; complete run → `movie_directed.json` + stale partial deleted; zero successes → nothing written.
  - **`--resume`**: reuses scenes that already have a prompt, re-plans only the rest. **Report**: directed / failed / retry count / skipped / failed scene ids.
  - Tests (39 new): 503/502/504/connection-timeout/read-timeout retry, terminal-error non-retry, retry ceiling, backoff-with-jitter bounds, isolation, partial save, resume. Sprint 022's tests updated to the new `(movie, report)` signature.
  - **Trade-off**: ~10× the requests for a ten-scene movie — materially more quota and wall-clock than the bulk call.

- **Sprint 022 — AI Director — done:**
  - New domain VOs `domain/value_objects/director.py`: `DirectorNotes` (the 16 specified fields), `DirectedScene(Scene)`, `DirectedMovie(Movie)` — **subclasses**, so `movie.py` is untouched and `movie_directed.json` still validates as a plain `Movie` (every existing stage can read it).
  - New `infrastructure/director/`: `DirectorService` (renders `prompts/director/shot_plan.md`, LLM JSON mode, **retry once**), pure `build_director_prompt()`, `notes_parser` (parse + **honest fallback** from the scene's own camera/action/emotion; no invented filler), reader/writer, `DirectorError`.
  - **`director_prompt` targets AI video models**: character-library identity first (the template forbids re-describing characters, preserving Sprint 019 consistency), then shot/camera motion, motion breakdown (subject/hands/pose/expression), secondary motion (hair/cloth/environment), lighting, mood, setting, duration, transitions, and a temporal-coherence directive.
  - New CLI `director --movie output/movie_consistent.json [--library]` → `output/movie_directed.json`. Every original scene field, including `video_prompt`, preserved verbatim.
  - Tests (60 new): models + JSON schema, prompt composition (video-targeting, library combination, omission of empty fields), fallback derivation and merge, parser (fences/nesting/bad ids/errors), service (retry, skipped scenes, determinism, no-library), CLI. No real API.
  - **Additive & isolated**: Movie Builder, Character Library, providers, image generation, TTS and compose all untouched; only `app.py` modified. Live: 10 scenes, all 16 fields populated, 5 distinct shot types, source `movie_consistent.json` unmodified.

- **Sprint 021A — Cost Guard — done:**
  - `video generate --dry-run`: prints provider, model, scene count, estimated jobs, estimated duration and estimated cost, then stops. **Builds no provider**, so it works without credentials.
  - `video generate --limit N`: submits only the first N scenes (`--limit 0` rejected by the CLI); the plan marks the run as limited.
  - **Confirmation** when `provider != mock` and no `--yes`: defaults to **No**; a non-interactive stream (CI/piped/closed stdin) declines. Declining exits **0** — a deliberate choice, not a failure.
  - New `video/providers/cost.py` (`GenerationPlan`, `build_plan`, `estimate_cost`) is the single source of truth for both the preview and the manifest estimates.
  - **Manifest (breaking)**: `cost` → `estimated_cost` + `actual_cost`; `total_cost` → `total_estimated_cost` + `total_actual_cost`. `0.0` means *unknown rate*, not free. Failed scenes keep their estimate but cost `0.0`.
  - Tests (27 new): plan/estimate purity, dry-run (no HTTP, no credentials, limit interaction), `--limit`, confirmation (accept/decline/default-No/closed-stdin/`--yes`/mock-never-prompts), and manifest costs. Existing Kling CLI tests updated to pass `--yes` — they were previously "submitting" unconfirmed paid jobs, which is exactly what this guard stops.

- **Sprint 021 — Kling Video Provider — done:**
  - New `infrastructure/video/providers/kling/`: `client.py` (`KlingClient` protocol + httpx `RealKlingClient` — the only module doing HTTP; translates every transport/HTTP error into the shared provider hierarchy), `models.py` (`KlingJob`, vendor `task_status` → `VideoJobStatus`; an unknown status counts as *running*, never a discarded job), `provider.py` (`KlingVideoProvider`).
  - **Image-to-video**: scene image + `video_prompt` → one clip. Lifecycle exposed as `submit_job()` / `poll_job()` / `download_result()` / `cancel_job()`, composed by `generate()`.
  - **Resilience**: shared `RetryPolicy` (exponential backoff on 429/503/timeout; terminal errors not retried), per-request `timeout` **plus** a separate `poll_timeout` for the whole remote render, and **cancellation on overrun** so no job is left billing. All failures → `VideoProviderError`; a provider outage is a clean per-scene failure and a non-zero exit, never a crash.
  - Config reuses the `VIDEO_PROVIDER` section (`API_KEY`/`BASE_URL`/`MODEL` = `KLING_*`, plus `POLL_INTERVAL`, `POLL_TIMEOUT`, `COST_PER_SECOND`). **`mock` remains the default** so the CLI works without paid credentials.
  - CLI `video generate --movie output/movie_consistent.json` (`--scene` alias kept; `--images` override): phase progress bar (submitting → waiting → downloading → completed), per-scene continue-on-failure, and `output/video_clips/manifest.json` (scene_id, provider, model, status, duration, cost, remote_job_id, filename + total_cost). Scenes match images by **position** (`001.png` → first scene).
  - `video doctor` now fails **only on the configured provider** — an unconfigured alternative driver is informational (a second driver made the old "any FAIL" rule wrong).
  - Tests (70 new): client payload/parsing, HTTP error mapping, retry/backoff, poll-timeout-and-cancel, download, manifest, CLI — all via httpx `MockTransport`; **no network**. `compose`, TTS and image generation untouched.
  - **Live Kling API unverified** (no credentials). Endpoint shapes follow Kling's published image-to-video docs; an end-to-end run was verified against a local stub HTTP server (submit → poll `processing`→`succeed` → download → manifest, with cost).

- **Sprint 020 — Video Provider Layer — done:**
  - New `infrastructure/video/providers/` subpackage (under the existing `infrastructure/video/`, per the sprint spec — a documented deviation from `infrastructure/providers/<capability>/`, ADR-027): `VideoProvider` Protocol (`generate`, `supported_models`, `health_check`, `name`), `VideoGenerationRequest` / `VideoGenerationResult` (vendor-neutral; `camera` reuses the domain `Camera` VO), `VideoJobStatus` (`queued`/`running`/`completed`/`failed`), `VideoProviderError`, and a `scene_reader` turning a movie's scenes into requests.
  - `VideoProviderRegistry`: register / names / is_registered / create / create_default / concurrent `health_check`. **Constructed, not module-global** (`build_default_registry()`), so no global mutable state.
  - New `VideoProviderSettings` (`AIVF_VIDEO_PROVIDER__PROVIDER|MODEL|TIMEOUT|RETRY_COUNT`), **separate** from the ffmpeg `VideoSettings` (`AIVF_VIDEO__*`), which are unchanged.
  - `MockVideoProvider` (**development only**): one clip per scene via the existing ffmpeg approach → `output/video_clips/scene_001.mp4`, …; reference image when present, colour card otherwise; honours timeout + retry; reuses the composer's injectable runner seam; health = WARN (not AI video) / FAIL without ffmpeg. New pure `build_clip_command()` — `ffmpeg_command.py` and `FfmpegVideoComposer` were **not modified**.
  - New CLI group `video providers` / `video doctor` / `video generate --scene output/movie_consistent.json` (per-scene table, continue-past-failure, non-zero exit if any failed).
  - Tests (52 new): registry (registration/lookup/duplicates/defaults/health, and that no commercial driver is registered), mock provider (pure argv, naming, retry, timeout, missing ffmpeg, health), configuration, CLI. ffmpeg is never invoked.
  - **Strictly abstraction only**: no Veo / Kling / Runway / Hailuo integration. Backward compatible — `compose` and every existing command behave exactly as before.

- **Sprint 019 — Character Consistency Engine — done:**
  - New domain VOs `domain/value_objects/character_library.py`: `CharacterLibrary`, `CharacterProfile`, `NormalizedAppearance` (hair/eyes/face/body), `NormalizedOutfit` (clothes/accessories) — frozen, matching the `character_library.json` schema exactly.
  - New `infrastructure/character/`: `CharacterConsistencyService` (normalize appearance/outfit, one `master_prompt` per character, merged negative prompt, **deterministic seed** = SHA-256 of the id, **duplicate merge** first-wins), `CharacterPromptInjector` (prepend master / append negative / preserve original; **idempotent**; unknown character id → error), plus reader/writer/errors. **No AI provider, no network** — byte-identical output on every run.
  - New CLI group `character build --input output/movie.json` → `output/character_library.json`; `character inject --movie output/movie.json [--library]` → `output/movie_consistent.json` (a full, schema-valid `Movie`).
  - Tests (37 new): library models + JSON schema, normalization, seed generation, master/negative prompt generation, duplicate merge, injection (incl. idempotence, multi-character, unknown id), CLI (build/inject/missing files/explicit library/no side effects).
  - **Additive & isolated**: the Movie Builder, image provider, TTS and compose were not modified; `movie.json` is never mutated. Added `CharacterLibraryError`. Live: 4 profiles with distinct seeds, 10/10 scenes injected, originals preserved.

- Architecture Document (canonical) — **done**.
- Full documentation set in `docs/` (`00`–`13`, `CHANGELOG`) — **done**.
- ADR-001 … ADR-025 recorded — **done**.
- **Sprint 018 — Character & Scene Bible (Movie Builder) — done:**
  - New domain VOs `domain/value_objects/movie.py`: `Movie`, `Character`, `Appearance`, `Location`, `Camera`, `Scene` (frozen; match the `movie.json` schema exactly). Camera nested; action/emotion/dialogue are Scene string fields.
  - New infra `MovieBuilder` (`story/movie_builder.py`) + `movie_parser.py` (dedup characters by id → **fixed appearance**; inject style/genre/duration) + `movie_writer.py` + `prompts/story/movie.md`. Mirrors the existing generator pattern (LLM JSON mode, retry-once).
  - New CLI `movie --input output/chapter.json [--style --genre --language]` → `output/movie.json`. Reuses `read_chapter`; writes only `movie.json`.
  - Tests (21 new): domain schema/immutability, parser (dedup/inject/fences/errors/**schema validation**), builder (extraction/scenes/retry, fake provider), CLI (build/save/schema-valid output/missing-chapter/no-side-effects).
  - **Additive & isolated**: no existing generator, image pipeline, TTS, or compose was modified; all 12 commands still register. Added a `MovieBuildError`. Live: real schema-valid `movie.json` (4 deduped characters w/ fixed appearance, 5 locations, 8 scenes, camera/action/emotion/prompts).
- **Sprint 017 — Video Composer — done:**
  - New `infrastructure/video/`: pure `build_ffmpeg_command()` (argv generator), `parse_srt_cues()` (timing), `FfmpegVideoComposer` (implements the existing `VideoComposer` protocol — no new port, no factory), `write_video_metadata`.
  - ffmpeg-only, 1080x1920/30fps/H.264/AAC; one image per subtitle cue (reuse **last** image if fewer images than cues); per-image Ken Burns `zoompan`; `xfade` crossfades; burned subtitles (`subtitles` filter, Windows-escaped); `-shortest` narration audio.
  - Subprocess runs off the event loop (`asyncio.to_thread`, injectable runner); **retry once** on non-zero exit → `MediaError`; missing binary → `MediaError` (graceful).
  - CLI `compose --images --audio --subtitle`: verifies ffmpeg with the existing `check_ffmpeg()` diagnostics (clear "install FFmpeg" message if absent), reads-only (never regenerates assets), writes `output/video/final.mp4` + `metadata.json` (duration/fps/resolution/image_count/subtitle_count).
  - Tests (26 new): command generation, srt timing, composer (retry/missing-ffmpeg/reuse-last/errors) with a **mocked runner**, CLI (success/missing-ffmpeg/missing-inputs), settings. No ffmpeg invoked.
  - `VideoSettings` added; ffmpeg not installed on this machine → `compose` exits 1 with a friendly message (verified). Operator will install ffmpeg and run the live compose.
- **Sprint 016 — Subtitle Generation — done:**
  - New `infrastructure/providers/transcription/` layer: `TranscriptionProvider` protocol + models (`TranscriptionRequest/Segment/Result`), `GeminiTranscriptionProvider` behind a `GeminiTranscriptionClient` seam (lazy SDK; inline audio → JSON timed segments), `TranscriptionProviderFactory` (`gemini_transcription` driver; api-key falls back to the LLM key), `TranscriptionProviderSettings` (retry ×3, default model `gemini-flash-latest`, language `vi`).
  - Pure `to_srt()` formatter (`transcription/base/srt.py`) + `media/subtitle_storage.py` (UTF-8 `.srt`). Provider returns data; the CLI writes the file.
  - CLI `subtitle --audio --chapter [--language vi] [--force]`: skip-if-exists, progress spinner, `_ensure_utf8_stdout` (legacy-Windows safe). Reads `chapter.json` (reference text) + narration audio → `output/subtitles/narration.srt`.
  - Tests (30 new): SRT formatter, subtitle storage, provider (retry/timeout/health/no-key), factory, reply parser, CLI (generate/skip/force/missing-audio/missing-chapter), settings defaults. No real API in tests.
  - Live: 21-cue Vietnamese `.srt` produced (SubRip, UTF-8) from the Sprint-015 narration. Asset pipeline (`SubtitleGenerator` contract) untouched.
- **Sprint 015 — Voice Generation — done:**
  - `tts` command primary flag is now **`--input`** (`--chapter` kept as a backward-compatible alias); reuses `SpeechProvider`, default language `vi`.
  - Retry ×3 (`SpeechProviderSettings.retry_count`) and skip-unless-`--force` were already present; `narration.mp3` + `metadata.json` (duration/voice/provider/sample_rate) unchanged.
  - **Fixed a real defect**: on legacy Windows (cp1252) the Rich spinner's Braille glyphs crashed the process *after* saving `narration.mp3` but *before* `metadata.json` — the command now switches stdout to UTF-8 first, so Vietnamese text and progress glyphs render and both files are always written.
  - Tests: added `test_tts_command_accepts_input_flag`; existing skip/force/metadata tests updated to `--input`. Verified live end-to-end.
- **Sprint 014 — Generate Real Images — done:**
  - `image` command reworked to iterate prompts with a 1-based index → `NNN.png`: **per-file skip** (unless `--force`), **continue on failure**, and a **generated / skipped / failed** summary table.
  - Manifest schema upgraded (`ImageManifestEntry`): `index, filename, prompt, provider, model, width, height, created_at`. Dimensions read from the actual image bytes via a dependency-free PNG/JPEG parser (`media/image_dimensions.py`).
  - Retry ×3 unchanged (provider's `ImageRateLimiter`). Provider saves into a work dir; each image is atomically renamed to its index-aligned name (provider/storage/public APIs untouched).
  - Tests: `test_image_dimensions.py` + reworked `test_image_cli.py` (generate/manifest/skip/force/continue-on-failure/retry, mocked provider). Live: 6 existing images skipped, manifest rebuilt with real `576×1024` dimensions.
  - Fixed a legacy-Windows cp1252 crash (removed a `→` from the summary line).
- **Sprint 013 — Pollinations Image Provider — done:**
  - New `providers/image/pollinations/` — `PollinationsImageProvider` (implements the `ImageProvider` protocol) + `PollinationsClient` seam + httpx-backed `RealPollinationsClient` (only module doing HTTP). No API key required.
  - Registered as the `pollinations` driver in `ImageProviderFactory`; **default image provider flipped to `pollinations`** (model `flux`) in settings + `.env.example`. Gemini Imagen unchanged and available via `provider=gemini_imagen`.
  - Reuses the existing `image` command unchanged: reads `output/image_prompts.json`, saves `001.png`…, manifest, retry ×3 (shared `ImageRateLimiter`), skip-existing-unless-`--force`. Aspect ratio → width/height (longer side 1024).
  - Tests: `test_pollinations_provider.py` (fake client) + `test_pollinations_client.py` (httpx `MockTransport`, no network) + factory/settings updates. No public API changed; no other provider modified.
  - Live: 6 images generated for free (`provider=pollinations`, `model=flux`).
- **Sprint 012 — Implement Image Generation (image hardening) — done:**
  - Enhanced the existing `image` command (Sprint 008) — reuses `ImageProvider`, no refactor:
    - **Filenames**: images now saved as `001.png`, `002.png`, … (`ImageStorage` gained backward-compatible empty-prefix support; default prefix unchanged, so the asset pipeline still uses `image_001.png`).
    - **Manifest**: writes `output/images/manifest.json` (count + per-image index/path/provider/model/generation_time) via new `providers/image/base/writer.write_images_manifest`.
    - **Retry ×3**: `ImageProviderSettings.retry_count` default 1 → **3**.
    - **`--force` / skip**: skips generation when `output/images/001.png` exists, unless `--force`.
  - Progress bar unchanged.
  - Tests: 241 total (4 new — empty-prefix storage, manifest, skip-without-force, `--force`; existing image CLI test updated to `001.png`).
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 013 — Voice Generation (tts hardening) — done:**
  - Enhanced the existing `tts` command (Sprint 010) — reuses `SpeechProvider`, no refactor:
    - **Retry ×3**: `SpeechProviderSettings.retry_count` default 1 → **3** (RetryPolicy retries transient errors 3 times).
    - **`--force` / skip**: if `output/audio/narration.mp3` exists, generation is skipped (exit 0) unless `--force` is passed.
  - Output/metadata unchanged (`narration.mp3` + `metadata.json` with duration/sample_rate/provider/voice); progress bar unchanged.
  - Tests: 237 total (4 new — settings retry-3 default, provider retry-3 behavior, skip-without-force, `--force` regenerates).
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 011 — Asset Pipeline Foundation — done:**
  - `infrastructure/asset_pipeline/`: uniform `AssetResult` (success/path/duration/metadata); generator Protocols `ImageGenerator`, `SpeechGenerator`, `SubtitleGenerator`, `VideoComposer`; `AssetPipelineRunner` (`generate_images`/`generate_voice`/`generate_subtitles`/`compose_video`).
  - `ImageAssetGenerator` / `SpeechAssetGenerator` adapters **delegate to the existing `ImageProvider` / `SpeechProvider`** (real, no duplication). Subtitle/video are contracts only → the runner raises `AssetStageUnavailableError` until their sprints.
  - CLI `ai-video-factory assets` shows a status table (images/voice ready; subtitles/video pending) — no generation.
  - No actual TTS/image/subtitle/ffmpeg/video work (foundation only).
  - Tests: 233 total (8 new — AssetResult, adapters, runner orchestration + stage status, `assets` CLI); no real API calls.
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 010 — Voice Generator — done:**
  - `SpeechProvider` Protocol (`synthesize`, `health_check`, `list_voices`) + `SpeechSynthesisRequest`/`SpeechSynthesisResponse` in `infrastructure/providers/speech/base/`.
  - `GeminiSpeechProvider` (google-genai Gemini TTS) behind a `GeminiTtsClient` seam (SDK lazily imported); saves via `AudioStorage`, retries transient errors once. Reuses shared errors/retry/health.
  - Gemini TTS returns PCM → wrapped into WAV (pure-Python `wave`, no ffmpeg) and saved as `output/audio/narration.mp3`; `metadata.json` (duration, voice, provider, sample_rate).
  - `SpeechProviderFactory.create(settings, storage)` — config-driven; speech key falls back to the LLM key. `SpeechProviderSettings`.
  - CLI `ai-video-factory tts --chapter <chapter.json>` → Rich spinner + summary; graceful exit 1.
  - Tests: 225 total (23 new — models, audio storage + PCM→WAV, Gemini TTS provider with fake client, factory, CLI); no real API calls.
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 009 — Pipeline Orchestrator (Phase 1) — done:**
  - `PipelineRunner` (`infrastructure/pipeline/`) composes the existing four generators — no new business logic. Sequential stages; each output persisted immediately; any failure stops the run (earlier outputs kept). One shared provider + prompt service across all stages.
  - `PipelineRequest` / `PipelineResult` typed models; progress via an injected `on_stage` callback (runner stays Rich-free).
  - CLI `ai-video-factory generate --topic --style --platform [--chapters]` → Rich progress (`[1/4] …`) + summary; writes `output/{ideas,story_outline,chapter,image_prompts}.json`. Graceful exit 1 on failure.
  - **No image generation / TTS / subtitle / ffmpeg / upload** (strict rule honored).
  - Tests: 198 total (3 new integration — runner produces all outputs, stop-on-failure, `generate` CLI end-to-end, with a stage-aware fake provider); no real API calls.
  - Verified end-to-end against the live API (all four files produced). Ruff, MyPy (strict), Pytest all green.
- **Sprint 008 — Image Provider Layer — done:**
  - `ImageProvider` Protocol (`generate`, `health_check`, `models`) + `ImageGenerationRequest` / `ImageGenerationResponse` in `infrastructure/providers/image/base/`.
  - `GeminiImagenProvider` (google-genai Imagen) behind an `ImagenClient` seam (SDK lazily imported); saves via `ImageStorage`, retries transient errors once. Reuses the shared `AIProviderError`/`RetryPolicy`/`ProviderHealth`/`HealthStatus`.
  - `ImageProviderFactory.create(settings, storage)` — config-driven, no hardcoded provider; image API key falls back to the LLM key.
  - `ImageStorage` (`infrastructure/media/`) writes sequential `image_001.png`, `image_002.png`, … to `output/images/`.
  - Config: `ImageProviderSettings` (provider/api_key/model/timeout/retry_count).
  - CLI `ai-video-factory image --input <image_prompts.json>` → Rich progress bar + summary; graceful exit 1.
  - Tests: 189 total (20 new — request/response models, storage, Imagen provider with fake client, factory, CLI); no real API calls.
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 007 — Image Prompt Generator — done:**
  - Domain value object `ImagePrompt` (scene_number, prompt, negative_prompt, aspect_ratio, style, camera, lighting, character_reference, environment, seed?).
  - `infrastructure/story/`: `ImagePromptGenerator` (renders `image/image_prompt.md`, provider from `ProviderFactory` in JSON mode, parse + retry once), `parse_image_prompts` (injects project-level style/aspect_ratio), `ImagePromptParseError`, `read_chapter`, `write_image_prompts_json`.
  - Prompt `image/image_prompt.md` rewritten to a JSON `{image_prompts:[…]}` template (vars: chapter_title, chapter_content, style, aspect_ratio, count, language).
  - CLI `ai-video-factory image-prompt --chapter <path> [--style --aspect-ratio --count --language]` → Rich table + `output/image_prompts.json`; graceful exit 1.
  - Text only — no images generated (ADR-017).
  - Tests: 169 total (19 new — image-prompt model, parser, chapter reader, generator with fake provider, CLI); no real API calls.
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 006 — Chapter Generator — done:**
  - Domain value object `StoryChapter` (title, content, estimated_duration_seconds).
  - `infrastructure/story/`: `ChapterGenerator` (renders `story/chapter.md` from the outline, provider from `ProviderFactory` in JSON mode, parse + retry once), `parse_chapter` + `estimate_duration_seconds` (computed, not LLM-trusted), `ChapterParseError`, `read_outline`, `write_chapter_json`.
  - Prompt `story/chapter.md` rewritten to a JSON `{title, content}` template driven by the outline fields.
  - CLI `ai-video-factory chapter --outline <path> [--language]` → Rich chapter view + `output/chapter.json`; graceful exit 1 on any `AppError`.
  - Interpretation: the whole outline is rendered as one narration chapter (single input arg, single output); recorded in ADR-016.
  - Tests: 150 total (20 new — chapter model, parser/estimator, outline reader, generator with fake provider, CLI); no real API calls.
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 005 — Story Outline Generator — done:**
  - Domain value objects `StoryOutline` (title, genre, world_setting, cultivation_system, main_character, supporting_characters, antagonist, story_arc, ending, chapter_outlines) and `ChapterOutline` (chapter_number, title, summary, cliffhanger).
  - `infrastructure/story/`: `OutlineGenerator` (renders `story/outline.md`, provider from `ProviderFactory` in JSON mode, parse + validate, retry once), `parse_outline` (chapter-count + required-field + non-empty validation), `OutlineParseError`, `read_idea` (select from ideas JSON), `write_outline_json`.
  - Prompt `story/outline.md` rewritten to a JSON `StoryOutline` template (vars: idea_title, idea_hook, idea_summary, target_duration, chapter_count, language).
  - CLI `ai-video-factory outline --idea <path> [--index --chapters --duration --language]` → Rich tables + `output/story_outline.json`; graceful exit 1 on any `AppError`.
  - Shared `console_io.emit_renderable` (UTF-8-safe) extracted; `idea_presenter` reuses it.
  - Tests: 130 total (22 new — outline models, parser, idea reader, generator with fake provider, CLI); no real API calls.
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 004 — Story Idea Generator — done:**
  - Domain value objects `IdeaBrief` (topic/style/target_platform/language) and `StoryIdea` (title/hook/summary/tags) in `domain/value_objects/idea.py` (first domain content).
  - `infrastructure/story/`: `IdeaGenerator` (renders `story/idea.md`, calls `LLMProvider` from `ProviderFactory` in JSON mode, parses + validates, retries once), `parse_ideas`, `IdeaParseError`, `write_ideas_json`.
  - Prompt `story/idea.md` evolved to a multi-idea JSON template (vars: topic, style, target_platform, language, count).
  - CLI `ai-video-factory idea --topic --style --platform [--language]` → Rich table + `output/ideas.json`; graceful exit 1 on any `AppError` (e.g. missing key).
  - Tests: 108 total (17 new — models, parser, generator with fake provider, CLI; 2 Sprint 003 prompt tests updated for the new idea.md vars); no real API calls.
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 003 — Prompt Engine — done:**
  - Prompt templates under configurable root `prompts/` (`story/{idea,outline,chapter,scene}.md`, `image/image_prompt.md`) — no prompt text in Python.
  - `infrastructure/prompts/`: `PromptLoader` (load + cache + `PromptNotFoundError`), `PromptRenderer` (Jinja2, `StrictUndefined`), `PromptValidator` (exists + syntax + required vars), `PromptService` (`render`, `validate`, `list_prompts`).
  - Errors: `PromptError → PromptNotFoundError/PromptValidationError/PromptRenderError` (extend `InfrastructureError`).
  - Config: `PromptSettings.root` (default `prompts/`, env `AIVF_PROMPTS__ROOT`).
  - CLI: `prompt list` / `prompt show <name>` / `prompt validate` / `prompt render <name> --var k=v` (UTF-8-safe raw output).
  - Tests: 91 total (26 new — loader, renderer, validator, service incl. shipped templates, CLI).
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 002 — AI Provider Layer — done:**
  - LLM provider contract in `infrastructure/providers/base/`: `LLMProvider` Protocol (`generate`, `health_check`, `count_tokens`, `models`); models `LLMRequest`, `LLMResponse`, `TokenUsage`, `RawCompletion`, `ProviderHealth`.
  - Provider error hierarchy (`AIProviderError` → `AuthenticationError`, `RateLimitError`, `TimeoutError`, `ProviderUnavailableError`, `InvalidResponseError`) extending the `AppError`/`ProviderError` tree.
  - `RetryPolicy` (exponential backoff, retries only 429/503/timeout); configurable per-request timeout via `asyncio.wait_for`.
  - `GeminiProvider` (first provider) over the official `google-genai` SDK, isolated behind a `GeminiClient` seam (SDK lazily imported); API key read from settings.
  - `ProviderFactory.create()` — config-driven provider selection (unknown provider → `ConfigurationError`).
  - Configuration: `ProviderSettings` (`provider`, `api_key` as `SecretStr`, `model`, `timeout`, `retry_count`).
  - `doctor` gains an AI-provider health check returning OK/WARN/FAIL (WARN when no key); diagnostics now tri-state via `shared/health.HealthStatus`.
  - Tests: 65 total (35 new — models, errors, retry, Gemini with a fake client, factory, settings, diagnostics); no real API calls.
  - Ruff, MyPy (strict), Pytest all green.
- **Sprint 001.5 — Foundation Review Fix — done:**
  - `.gitignore` expanded (caches, venvs, coverage, logs, `output/*`/`data/*` with `.gitkeep` negations, `.env`, IDE/OS files).
  - `.gitkeep` placeholders in `logs/`, `output/`, `data/`; runtime artifacts removed from the working tree (folders preserved).
  - `CLAUDE.md` rewritten: project role, architecture rules, sprint rules, coding rules, review rules, hard "do not" list.
  - `.editorconfig` (UTF-8, LF, 4-space, trim trailing whitespace, final newline; Markdown/Makefile/YAML overrides).
  - `Makefile` (install, sync, lint, format, typecheck, test, doctor, run, clean, hooks).
  - `.pre-commit-config.yaml` (ruff check, ruff format, mypy; pytest as a manual stage); `pre-commit` added to dev extras.
  - Validation: Ruff, MyPy, Pytest (30) all green; `factory version`/`doctor` run.
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

`feat/sprint013-voice-generation`. `main` is protected.

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

**AI provider layers (infrastructure):**

| Capability | Contract | Active driver | Adapter | Status |
|---|---|---|---|---|
| LLM completion (Sprint 002) | `LLMProvider` (Protocol) | `gemini` | `GeminiProvider` (`google-genai`) | **implemented** |
| Image generation (Sprint 008) | `ImageProvider` (Protocol) | `gemini_imagen` | `GeminiImagenProvider` (`google-genai` Imagen) | **implemented** |
| Speech / TTS (Sprint 010) | `SpeechProvider` (Protocol) | `gemini_tts` | `GeminiSpeechProvider` (`google-genai` TTS) | **implemented** |

Future drivers plug in by registering a builder in the respective factory (`ProviderFactory` / `ImageProviderFactory` / `SpeechProviderFactory`); no existing code changes (ADR-005).

**Story generators (Sprint 004–007):** `IdeaGenerator`, `OutlineGenerator`, `ChapterGenerator`, `ImagePromptGenerator` (infrastructure/story). **Image generation (Sprint 008):** `image` CLI → PNGs in `output/images/`. **Pipeline (Sprint 009):** `PipelineRunner` composes the four generators; `generate` runs the whole chain in one command. File-based chain: `ideas.json → story_outline.json → chapter.json → image_prompts.json` (→ `output/images/*.png` via `image`).

## 8. Modules (layer readiness)

| Layer | Package | Status |
|---|---|---|
| Domain | `src/ai_video_factory/domain/` | **value_objects (IdeaBrief, StoryIdea, StoryOutline, ChapterOutline, StoryChapter, ImagePrompt, Movie/Character/Appearance/Location/Camera/Scene, CharacterLibrary/CharacterProfile, DirectorNotes/DirectedScene/DirectedMovie)** implemented |
| Application | `src/ai_video_factory/application/` | package marker only (populated later) |
| Infrastructure | `src/ai_video_factory/infrastructure/` | **config, logging, diagnostics, providers (llm + image + speech + transcription), prompts, story, character, director, media, video (compose + provider layer), pipeline, asset_pipeline** implemented |
| Interface | `src/ai_video_factory/interface/` | **cli (version/doctor/prompt/idea/outline/chapter/image-prompt/movie/character/director/image/generate/tts/subtitle/compose/video/assets), presenters** implemented |
| Shared | `src/ai_video_factory/shared/` | **health** implemented |

## 9. Current Tasks

- [x] `character_memory.json` with every documented canonical field, reference image and appearance hash.
- [x] First successful image per character adopted as the canonical reference, never re-pointed.
- [x] Every prompt carries reference image, appearance summary and previous generated appearance.
- [x] `AppearanceValidator` (8 attributes); below 90 the prompt is rebuilt. `appearance_scores.json` written.
- [x] Reference attached where a provider supports it, described otherwise. No provider, video or compose change; backward compatible.
- [x] `VisualContinuityEngine`: storyboard + bibles -> `visual_context.json`.
- [x] Every shot carries previous/current/next, scene goal, character state, emotion and the six continuity axes.
- [x] Image prompts rebuilt from every source, never the current shot alone.
- [x] `PromptScorer` (5 dimensions, threshold 90) recomposes anything below it; outputs `prompt_scores.json`.
- [x] No provider changes, no video changes; `image_prompts.json` untouched.
- [x] `storyboard.json` -> `output/video_clips/shot_NNN.mp4` + `manifest.json`.
- [x] Clips are 4-8s (shots merged within scene boundaries; short clips reported), portrait 1080x1920 from `VideoSettings`.
- [x] `VideoProvider.generate(request, references)` with character / scene / previous-clip references; mock kept for tests.
- [x] `video generate --storyboard` + `--resume`; Director, Storyboard and Compose untouched.
- [x] OpenRouter provider added behind the existing `LLMProvider` interface; director uses it; default `deepseek/deepseek-chat-v3`.
- [x] `AIVF_DIRECTOR_PROVIDER` / `AIVF_OPENROUTER_API_KEY` / `AIVF_OPENROUTER_MODEL` honoured verbatim.
- [x] `storyboard` CLI: `movie_directed.json` -> `storyboard.json`, 20 fields per shot, narration mapped onto the timeline.
- [x] Tests: storyboard generation, duration validation, timeline validation, CLI. No provider or compose logic changed.
- [x] Director calls the LLM **exactly once** per movie; prompt carries all scenes, the character library and the locations.
- [x] Every scene carries 3-8 shots (capped by its length) of 2-5s each, with all 13 required shot fields.
- [x] Batch JSON parsed and merged back into `movie_directed.json`; retry only the whole request.
- [x] Tests: batch parsing, shot generation, JSON validation, CLI.
- [x] Movie Builder, Character Library, video providers and compose untouched.
- [x] Director calls Gemini **once** per run; prompt carries all scenes + character library + locations.
- [x] Response mapped back to the movie by `scene_id`; invalid JSON re-asks the whole request (never per scene).
- [x] Tests updated for single-request semantics.
- [x] Retry on 502/503/504 + connection/read timeouts (transport errors now translated at the SDK boundary).
- [x] Exponential backoff 1s/2s/4s/8s/16s, max 5 retries, ±20% jitter.
- [x] Per-scene independence — a failed scene never stops the others.
- [x] Final report (directed / failed / retry count) and partial save to `movie_directed.partial.json`.
- [x] `--resume` skips completed scenes and regenerates only the failed ones.
- [x] Unit tests (39 new); no unrelated modules modified.
- [x] `DirectorService`: `movie_consistent.json` → `movie_directed.json`, 16 director fields per scene.
- [x] `director_prompt` combining character library + scene + camera + cinematic + motion + environment, aimed at video models.
- [x] `director` CLI; tests (generation, schema, prompt, CLI).
- [x] Movie Builder, Character Library, providers, image generation and compose untouched.
- [x] `--dry-run` (provider, model, scene count, jobs, duration, cost; submits nothing, needs no key).
- [x] `--limit N` (first N scenes only).
- [x] Confirmation for paid providers unless `--yes`; defaults to No; non-interactive declines.
- [x] Manifest `estimated_cost` + `actual_cost`.
- [x] Unit tests (27 new); no unrelated refactoring.
- [x] `KlingVideoProvider` implementing `VideoProvider` (image-to-video).
- [x] `submit_job` / `poll_job` / `download_result` / `cancel_job`.
- [x] `KLING_API_KEY` / `KLING_BASE_URL` / `KLING_MODEL` via the existing `VIDEO_PROVIDER` section.
- [x] Network retry with exponential backoff, per-request timeout, poll timeout + cancel-on-overrun.
- [x] `video generate --movie` → `scene_NNN.mp4` + `manifest.json`; phase progress bar; clean error on outage.
- [x] compose / TTS / image generation untouched; existing provider architecture reused.
- [x] Ruff + MyPy(strict) + Pytest passing (533 tests, no network); end-to-end verified against a local stub HTTP server.

## 10. Next Tasks

- **Operator action:** supply Kling credentials (`AIVF_VIDEO_PROVIDER__API_KEY`) and set `PROVIDER=kling` to validate the driver against the live API — the only remaining unknown in Sprint 021. Install ffmpeg to unblock `compose` and the `mock` driver.
- Await next Sprint spec from the Lead. Ready when specified: **pointing the video stage at `director_prompt`** (nothing consumes it yet), pointing the image stage at `movie_consistent.json`, injecting `FfmpegVideoComposer` into `AssetPipelineRunner`, and composing generated clips into the final MP4 — **only build when specified**.

## 11. Known Issues

- `factory doctor` reports **FFmpeg: FAIL** on machines without ffmpeg installed (expected — documented runtime dependency, `08_ENVIRONMENT.md`). Not a code defect.
- `RealGeminiClient` (live `google-genai` calls) is not exercised by the test suite by design (tests use a fake client — no real API calls). It is covered manually via `doctor` when a key is configured.
- import-linter is not yet wired as an automated gate (layer boundaries upheld by construction/review). Tracked for a later tooling pass.

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
| Sprint | 025C — Character Memory Engine (delivered) | 2026-07-20 |
| Roadmap progress | ~66% | 2026-07-20 |
| Asset stages | images/voice ready; subtitles/video pending in the asset pipeline (standalone CLIs exist) | 2026-07-20 |
| AI providers implemented | 6 (gemini LLM, gemini_imagen, pollinations, gemini_tts, gemini_transcription, **kling video**) + the `mock` dev video driver | 2026-07-20 |
| Prompt templates | 7 (story×5, image×1, director×1) | 2026-07-20 |
| Tests | 899 passing | 2026-07-20 |
| Open tech-debt items | 6 | 2026-07-20 |
| Gates (Ruff / MyPy / Pytest) | all green | 2026-07-20 |

---

### Update discipline

At every session end, refresh: **Current Sprint, Completed, In Progress, Current Branch, Current/Next Tasks, Known Issues, Blocked By, Roadmap Progress, Metrics, Last updated**. Then update `13_SESSION_HANDOFF.md` and, at sprint close, `01_AI_CONTEXT.md` and `CHANGELOG.md`.
