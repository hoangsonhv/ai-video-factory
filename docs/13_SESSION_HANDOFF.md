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

**Session date:** 2026-07-20
**Author:** Senior Python Engineer
**Sprint:** 026 (second spec) — Cinematic Shot Planner (delivered)
**Version:** 0.1.0-dev
**Branch:** `main` (working tree; Sprint 018–022A files still uncommitted alongside)

### What was accomplished this session
- **Every frame is now planned, and the film is validated as a whole** (ADR-040). New `shot-plan` stage: `storyboard.json` -> `shot_plan.json` + `shot_statistics.json`, prompts rebuilt from the plan.
- **Diagnosed the "identical portraits" complaint before building.** Three causes, none of them the image provider:
  - **The storyboard itself asks for tight framing**: 9 of 30 shots are `close-up` and 9 more are `medium shot` - 60% of the film is framed tight before a prompt is composed.
  - **The prompts never said what else was in the frame**, so a model given a character and a mood drew a character on a backdrop.
  - **Nothing measured the film as a whole**, so every individually-defensible close up summed to thirty portraits.
  - Worth knowing: **the 30 images on disk were generated at 21:56, before the cinematic director ran at 22:18**, so they were never evidence about ADR-039 either way. The defects above are real regardless.
- **Coverage now follows content**: each scene is classified (opening / conversation / action / combat / emotion / landscape) and that kind's mandated size opens and dominates the scene. Read strictly, "conversation → medium for every shot" would recreate the monotony being removed - that interpretation is flagged in ADR-040 rather than hidden.
- **The distribution is enforced, not hoped for**: close <=20%, medium 20-35%, wide/full body >=40%, establishing >=5%, re-planned automatically. Rebalancing demotes the least-justified shot first and **never** trades away a size a scene's kind mandates.
- **A frame stating nothing at any depth is rejected** - that is precisely the shot that comes back as a face on a blank backdrop. Nothing is invented; a depth with no source stays empty.
- **Portrait prevention runs both ways**: banned framing is stripped from the source text (the words are the storyboard's) and raises if any survives, and a non-close shot refuses portrait framing in its **own negatives** - telling a model what not to frame beats hoping the positive text outweighs its bias toward faces.
- **Three defects found during verification, two caught by the tests:**
  - the re-plan cap was a fixed 12, so a skewed 20-shot film needing 21 changes stopped half-way and still reported itself re-planned while 40% close ups. The cap now scales with the film.
  - the negative prompt repeated the same boilerplate five times - de-duplication compared whole strings instead of terms.
  - `"golden"` was read as a time of day, so a midnight cemetery lit by a phone screen was lit as golden hour.
- 999 tests pass (64 new); Ruff and MyPy clean. Live on the real film: close **3.3%**, medium 33.3%, wide/full body **56.7%**, establishing 6.7%, valid after 3 re-plans; body **19 full / 10 waist / 1 head**.

### From earlier this session (Sprint 026, first spec)
- **The shot list is now directed rather than described** (ADR-039). New `cinema` stage: `storyboard.json` -> `cinematic_direction.json`, then `shot_image_prompts.json` recomposed with the direction folded in.
  - `SceneDirector` gives each scene a purpose, emotion, conflict and story beat (placed by where it falls in the film). `ShotDirector` gives each shot a type, angle, lens, composition, blocking, lighting, action and motion hint.
  - **85mm can no longer become the default** - the old `_lens_for()` inferred a lens from the word "close" in the storyboard camera string, so nearly every shot got a portrait lens. Lenses now come from a table keyed by shot size; 85mm is reachable only on a close up / extreme close up and alternates with 135mm there.
  - **Two coverage defects were caught during live verification and fixed**: lens alternation indexed by *global* position meant close ups always landed on 85mm and 135mm was unreachable (now counted per shot size); and the coverage cycle indexed only by `order`, so every scene of equal length was filmed shot-for-shot identically (now offset by the scene's position).
  - **Static actions are replaced, not decorated** - "standing" becomes walking / running / drawing a sword / casting a spell; a description that already carries a verb is kept, because the writer's words beat a generic substitute.
  - **A conflict nobody wrote is left empty.** `infer_conflict` reads the emotional register then the actions, and returns `""` when neither says anything - naming one would be invention.
  - `PromptComposer` rewritten to the director's order; `direction` is **optional**, so every 025B/025C caller composes exactly as before (their tests re-verified green).
- **Deterministic and offline** - no LLM call, no cost, the same storyboard always yields the same shot list. That is why it is rule-based rather than model-authored: coverage is craft, and rules that are written down can be tested.
- 935 tests pass (36 new); Ruff and MyPy clean. Live on the real film: 24mm x12, 35mm x7, 50mm x5, 85mm x3, 135mm x3 across six shot types.

### From the previous session (Sprint 025C)
- **Every prompt now restates a frozen character identity** (ADR-038), which is what stops a face changing between images.
  - `character_memory.json` holds the canonical face / hair / body / clothes / weapon / expression / palette, the reference image and an `appearance_hash`, plus gender / age / style for the validator.
  - **The canon is derived once then frozen.** A rerun reloads it and never overwrites a remembered value - only fills empty fields and adds newcomers. Hand edits survive; that is the intended way to fix a thin canon.
  - **The first image that exists for a character becomes its reference**, picked by walking the storyboard in timeline order, and is **never re-pointed** - doing so would redefine the character mid-film.
  - `AppearanceValidator` scores 8 attributes; below the threshold the prompt is rebuilt more insistently (summary -> identity lock -> every attribute pinned).
  - **Reference handling is provider-aware**: `PROVIDERS_WITH_IMAGE_REFERENCE` is empty because no shipped driver accepts an image and this sprint may not change one, so the reference is described in words. Adding a capable driver to that set attaches the path instead - no other change.
- **Unrecorded attributes score 0, not "n/a".** A character with no recorded weapon really will grow different ones; excusing it would report a perfect score for a prompt that pins nothing. Those show as `(not remembered)`.
- 899 tests pass. Live: average appearance score **97** across the real 30 prompts.


### From the previous session (Sprint 025B)
- **Image prompts are now composed from the whole film** (ADR-037), which is what makes consecutive stills match. Two spec gaps were settled with the Lead **before** building:
  - `character_bible.json` / `world_bible.json` did not exist -> **derived** from `character_library.json` and `movie_consistent.json`, then written out. A rerun reads them back and **keeps hand edits**.
  - `image_prompts.json` is owned by the `image` stage -> the new per-shot prompts go to **`shot_image_prompts.json`** instead, in the same `ImagePrompt` schema so a later sprint can repoint `image` without a migration.
- **Every prompt carries** character bible, world bible, visual context, previous / current / next shot, camera, lens, lighting, art direction, cinematic style and negatives. Continuity is asserted **only within a scene** - across a cut the world may legitimately change.
- **`PromptScorer`** grades five dimensions; below the threshold the prompt is **recomposed one level more explicit** (state -> insist -> repeat verbatim), so a retry actually changes the text. When the shortfall is missing upstream data, it is reported rather than looped over.
- **I caught and rewrote a scorer that always returned 100.** The first version excused absent data by dropping it from the denominator, which made every prompt perfect and the regeneration path dead code. It now counts absent data as a real deduction, so the score is diagnostic.
- 852 tests pass. Live: average **93/100** across 30 shots; `image_prompts.json` verified untouched.


### From the previous session (Sprint 025)
- **Storyboard -> AI video clips** (ADR-036). Two spec conflicts were resolved with the Lead **before** building:
  - **Resolution**: the spec said 1920x1080, the project is portrait 1080x1920 everywhere. Lead chose portrait; clips now carry `width`/`height`/`fps` from `VideoSettings`, so landscape is an env change, not a code change.
  - **Duration**: the spec said 4-8s clips, but shots are 2-5s (the real storyboard is 30 x 3s). Lead chose **merging adjacent shots** over clamping or exact-duration, so the 90s timeline is preserved exactly.
- **`clip_planner.plan_clips()`** groups consecutive shots **within one scene** into 4-8s clips. Scene boundaries are never crossed - a clip containing a hard cut would ask the provider for two places at once - so a scene that cannot split evenly yields one short clip, **which the CLI reports**.
- **Provider contract is now `generate(request, references)`.** `ClipReferences` carries character stills, the scene still and the **previous clip**; mock and Kling both updated. A provider supporting none of them ignores it.
- Clips are `shot_NNN.mp4`; the manifest records `clip_id` and `shot_ids` so the merge is auditable. `--resume` reuses clips already on disk without re-spending. `--movie` still works (Sprint 021 route).
- 805 tests pass. Verified on the real storyboard: 30 shots -> 20 clips, 90.0s preserved, portrait 1080x1920 @ 30fps, scene stills resolving to `output/images/NNN.png`.


### From the previous session (Sprint 024)
- **Two specs arrived labelled Sprint 024; both were delivered.**
- **OpenRouter is now the director's provider** (ADR-034): new `OpenRouterProvider` satisfying the **existing** `LLMProvider` protocol, behind an `OpenRouterClient` seam. `ProviderFactory.create_director()` reads `AIVF_DIRECTOR_PROVIDER` (default `openrouter`) so the director is chosen independently of the story pipeline. Config uses the flat names specified - `AIVF_OPENROUTER_API_KEY`, `AIVF_OPENROUTER_MODEL` (default `deepseek/deepseek-chat-v3`) - re-exposed as a typed `Settings.openrouter`. No business logic changed. `count_tokens()` estimates; OpenRouter has no counting endpoint.
- **New Storyboard stage** (ADR-035): `movie_directed.json` -> `storyboard.json`. Every shot flattened onto one timeline with absolute `speech_start`/`speech_end`, the `subtitle` spoken over it (mapped **by overlap**), an `audio_segment` clipped to the real track, a still-frame `image_prompt`, and the director's `video_prompt` carried through. **Durations are never rewritten** to chase the narration - drift is reported instead. Deterministic and offline.
- **Found a real data defect while verifying:** `output/subtitles/narration.srt` is timed to **109.5s** while `narration.mp3` is **66.7s**. Every subtitle mapped onto a shot is therefore misplaced - and the same mistiming would affect the burned-in subtitles at compose time. The storyboard CLI now warns when the two disagree by >10%.
- 770 tests pass. Live: storyboard built from the real directed movie - 30 shots, 10 scenes, 90.0s, contiguous timeline.


### From the previous session (Sprint 023)
- **Replaced the scene-level director with a shot planner** (ADR-033), keeping ADR-032's single-request rule:
  - `DirectorNotes`/`director_prompt` are **gone**; `DirectedScene.shots: tuple[Shot, ...]` takes their place. `Shot` carries the 13 specified fields.
  - **One LLM request per movie.** Prompt = all scenes + cast + locations; answer = one `{"scenes":[{"scene_id":n,"shots":[...]}]}` document. Retries re-ask that request (transient: backoff+jitter; unparseable: 3 attempts). Never per scene.
  - **3-8 shots, 2-5s each**, with the conflict resolved: `target_shot_count()` never asks for more shots than `duration // 2` allows, so a 5s scene gets 2.
  - **Parser repairs**: ids renumbered 1..N per scene, durations clamped (missing → even split of the scene), >8 shots trimmed.
  - **Each shot's `video_prompt` is composed** — library identity + camera/motion + setting + the model's own line + the video directive + library negatives.
- **Fixed an appearance leak found during verification.** `movie_consistent.json` prepends each character's master prompt to every scene prompt, so sending the scene text passed the appearance straight back to the director despite the cast section omitting it. `_beat()` now strips any library master prompt and the negative tail. A test pins it.
- Tests rewritten for shots; **667 pass.** Verified on the real 10-scene movie with a stubbed provider: 1 request, 30 shots, durations in range, ids renumbered, identity present, appearance absent.


### From the previous session (Sprint 022B)
- **Reverted 022A's per-scene planning to a single request** (ADR-032, supersedes ADR-031 §1–2). Per-scene calls exhausted a rate-limited key ~10× faster for no benefit the Lead wanted.
  - **One provider request per run.** The prompt carries every scene, the **character library** (ids + voice notes only — appearance deliberately omitted so ADR-026 consistency holds) and the **locations**. The model answers with one `{"scenes":[...]}` block, mapped back by `scene_id`.
  - **Retries re-ask that one request**: transient failures via the shared `RetryPolicy` (5 retries, 1s/2s/4s/8s/16s ±20% jitter); an unparseable answer re-asks the whole question up to `PARSE_ATTEMPTS` (3). Never per scene.
  - A scene the answer omits is left unplanned (empty `director_prompt`), saved to the partial file; `--resume` re-asks only those scenes — still one request.
  - Kept from 022A: Gemini transport-error translation, opt-in `RetryPolicy` jitter/`on_retry`, partial output, `--resume`, `DirectionReport`.
  - Tests rewritten for single-request semantics. **659 pass.**
- **Two issues measured during verification (both open, neither fixed here):**
  - The **`google-genai` SDK retries internally** — ~4 HTTP POSTs per logical `generate_content()` against a failing endpoint. Our 6 logical attempts became 24 requests. Our retry layer multiplies with the SDK's rather than replacing it.
  - **`RetryPolicy` under-waits when the server asks for longer than `max_delay`.** Gemini replied "retry in 51s"; we retried in 16.5s because the hint is capped by `max_delay=16` — guaranteeing another 429. One-line fix (honour the hint above the cap), but it affects every provider, so it was left for the Lead to approve.

### From the previous session (Sprint 022A)
- **Found and fixed the real defect.** 502/503/504 were *already* mapped to `ProviderUnavailableError` and retried. What was not handled: `RealGeminiClient` caught only `genai_errors.APIError`, which the SDK raises only once an HTTP response exists. A **connection timeout, read timeout or dropped socket** surfaced as a raw `httpx` exception — untranslated, unretried, and a breach of the "no raw vendor exceptions cross inward" rule. `map_transport_error()` now converts them to retryable provider errors at all three SDK call sites.
- **Per-scene planning.** The director issued **one** LLM call for the whole movie, so any final failure destroyed ten scenes of work. It now issues **one request per scene**, each carrying the previous scene's shot plan so cross-scene rhythm survives. This is what makes independent per-scene retry possible at all.
- **Retry**: 5 retries per scene, backoff 1s/2s/4s/8s/16s with **±20% jitter**, on 429/500/502/503/504 + connection/read timeouts; terminal errors (auth, malformed) are not retried. `RetryPolicy` gained **opt-in** `jitter` and `on_retry` parameters — defaults unchanged, so no other provider's timing moved.
- **Isolation**: a scene that exhausts its retries is left with empty `director`/`director_prompt` and the run continues. It is deliberately given **no** fallback notes — emptiness is precisely what `--resume` looks for.
- **Partial output**: some successes → `output/movie_directed.partial.json` + exit 1; a complete run → `movie_directed.json` and the stale partial is deleted; zero successes → nothing written.
- **`--resume`** reuses every scene that already has a prompt and re-plans only the rest. **Report** shows directed / failed / retry count / skipped / failed scene ids.
- Wired the director to `AIVF_PROVIDER__DIRECTOR_MODEL` (a field that appeared in `settings.py` mid-session) rather than leaving it as dead config.
- Tests: **39 new**; Sprint 022's tests updated to the new `(movie, report)` signature. **654 pass.**

### What was accomplished in the previous session (Sprint 022)
- New stage **Movie → Director → Directed Movie** (ADR-030), replacing generic video prompts with cinematic shot planning:
  - New domain VOs `domain/value_objects/director.py`: `DirectorNotes` (the 16 specified fields), `DirectedScene(Scene)`, `DirectedMovie(Movie)`. They **subclass** the Movie Builder's models — `movie.py` is untouched, and `movie_directed.json` still validates as a plain `Movie`, so every existing stage can read it.
  - New `infrastructure/director/`: `DirectorService` (renders `prompts/director/shot_plan.md`, LLM in JSON mode, **retry once**; one call plans the whole movie), **pure** `build_director_prompt()`, `notes_parser` (parse + fallback + merge), `reader.py`, `errors.py`.
  - New CLI `director --movie output/movie_consistent.json [--library <path>]` → `output/movie_directed.json`.
- **The shot plan is LLM-generated; the prompt composition is pure.** Fields like `hair_motion`/`cloth_motion`/`environment_motion` need to be read out of the scene's content, so a deterministic mapper could only emit filler — exactly the generic output this sprint removes. Assembling the prompt from those fields is deterministic and fully unit-tested.
- **Honest fallback, no filler**: a field the model omits is filled from what the scene already states (`camera`, `action`, `emotion`, movie `style`); anything no source can supply stays empty and is omitted from the prompt. A scene the model skips entirely still gets a plan from its own camera language.
- **Identity is never re-described** — the template explicitly forbids describing face/hair/clothing/build, so Sprint 019's consistency holds. Identity enters only via the library's `master_prompt`, prepended by the builder.
- **Original scene fields preserved verbatim**, including `video_prompt` — the director *adds*, never rewrites.
- Tests: **60 new** (models + JSON schema, prompt composition, fallback/merge, parser, service incl. retry & skipped scenes, CLI). **615 pass.**
- Verified live on the real 10-scene `movie_consistent.json`: all 16 fields populated, 5 distinct shot types, real secondary motion ("hair whips backward in the rushing wind", "neon signs blur past"), source file unmodified.

### What was accomplished in the previous session (Sprint 021A)
- **`video generate` can no longer spend money by accident** (ADR-029):
  - **`--dry-run`** → provider, model, scene count, estimated jobs, estimated duration, estimated cost; submits nothing. **Builds no provider**, so it needs no credentials — the preview must never be the thing that fails.
  - **`--limit N`** → only the first N scenes (`min=1`; `--limit 0` rejected by the CLI). The plan marks the run *limited* so a capped run is never mistaken for a full one.
  - **Confirmation** when `provider != mock` and no `--yes`: "This operation will submit X paid AI video job(s) … Continue? [y/N]". **Defaults to No**; a non-interactive stream (CI, piped, closed stdin) **declines**. Declining exits **0** — a deliberate choice, not a failure. `mock` never prompts.
- New **`video/providers/cost.py`** (`GenerationPlan`, `build_plan`, `estimate_cost`) — the single source of truth for both the dry-run preview and the manifest estimates, so the number shown before confirming is the number recorded after.
- **Manifest (breaking)**: `cost` → **`estimated_cost`** + **`actual_cost`**; `total_cost` → `total_estimated_cost` + `total_actual_cost`. A failed scene keeps its estimate but costs `0.0`. Both `0.0` = *unknown rate*, never *free*.
- Tests: **27 new** (plan purity, dry-run incl. no-HTTP/no-credentials, `--limit`, confirmation accept/decline/default-No/closed-stdin/`--yes`/mock-never-prompts, manifest costs). **560 pass.** Existing Kling CLI tests updated to pass `--yes` — they had been submitting unconfirmed paid jobs, which is precisely what this guard stops.
- Verified live against the real `movie_consistent.json`: dry run shows 10 scenes / 90.0s / 25.20 at $0.28/s; `--limit 2` shows "10 (limited to the first 2)" / 18.0s / 5.04; declining the prompt (and bare Enter) submits nothing and exits 0.

### What was accomplished in the previous session (Sprint 021)
- New **`infrastructure/video/providers/kling/`** — the first real AI video driver, behind the Sprint 020 contract:
  - `client.py`: `KlingClient` protocol seam + httpx `RealKlingClient` — **the only module doing HTTP**. `POST /v1/videos/image2video`, `GET /v1/videos/image2video/{id}`, `DELETE` for cancel, plus an unauthenticated CDN download (credentials are never sent to the CDN). Translates every transport/HTTP error into the shared provider hierarchy; pure `build_submit_payload()` / `parse_job()` are unit-tested without HTTP.
  - `models.py`: `KlingJob` + vendor `task_status` → `VideoJobStatus`. An **unknown status maps to RUNNING**, so a vendor vocabulary change stalls a poll rather than discarding a live job.
  - `provider.py`: `KlingVideoProvider` — image-to-video, with `submit_job()` / `poll_job()` / `download_result()` / `cancel_job()` composed by `generate()`.
- **Resilience**: shared `RetryPolicy` (exponential backoff on 429/503/timeout; auth/malformed are terminal and not retried), per-request `timeout` **plus** a separate `poll_timeout` bounding the whole remote render, and **cancel-on-overrun** so no job is left running and billing. All failures become `VideoProviderError` → a provider outage is a clean per-scene failure + non-zero exit, never a crash.
- **Config** reuses the existing `VIDEO_PROVIDER` section (no new section): `API_KEY`/`BASE_URL`/`MODEL` are `KLING_API_KEY`/`KLING_BASE_URL`/`KLING_MODEL`, plus `POLL_INTERVAL`, `POLL_TIMEOUT`, `COST_PER_SECOND`. **`mock` stays the default driver** — Kling needs a paid key.
- **CLI**: `video generate --movie output/movie_consistent.json` (`--scene` kept as a working alias; `--images` overrides the image dir). Phase progress bar (submitting → waiting → downloading → completed) driven by a provider callback; per-scene continue-on-failure; writes `output/video_clips/manifest.json` (scene_id, provider, model, status, duration, cost, remote_job_id, filename + total_cost).
- **`video doctor` behaviour change**: it now fails **only on the configured provider**. With two drivers registered, the old "any FAIL" rule wrongly failed the command because Kling has no key while `mock` is selected.
- ADR-028 recorded. Tests: **70 new** (client payload/parsing, HTTP error mapping, retry/backoff, poll-timeout-and-cancel, download, manifest, CLI) — all httpx `MockTransport`, **no network**. **533 pass.**
- **Verification:** the live Kling API is **unverified — no credentials were available.** An end-to-end run was verified against a local stub HTTP server: real `RealKlingClient` over a real socket, submit (bearer auth, base64 image, duration/aspect) → poll `processing`→`succeed` → download → two `scene_NNN.mp4` files + a correct manifest with cost.

### What was accomplished in the previous session (Sprint 020)
- New **`infrastructure/video/providers/`** subpackage — **the abstraction only, no commercial provider integrated**:
  - `VideoProvider` **Protocol** (`generate`, `supported_models`, `health_check`, `name`) — structural, matching the image/speech/transcription layers.
  - Vendor-neutral models: `VideoGenerationRequest` (scene_id, prompt, negative_prompt, duration, aspect_ratio, fps, seed, reference_images, camera, style, motion_level — `camera` reuses the domain `Camera` VO), `VideoGenerationResult` (scene_id, provider, model, status, remote_job_id, video_path, preview_path, duration, metadata), `VideoJobStatus` (`queued`/`running`/`completed`/`failed`), `VideoProviderError`, and `scene_reader` (movie JSON → requests).
  - `VideoProviderRegistry`: register / names / is_registered / create / create_default / concurrent `health_check`. **Constructed, never module-global** — `build_default_registry()` returns a fresh instance.
  - `MockVideoProvider` (**development only**): renders `output/video_clips/scene_001.mp4`, … with the existing ffmpeg approach (reference image when present, colour card otherwise); honours `timeout`/`retry_count`; reuses the composer's injectable `FfmpegRunner`; health = **WARN** (not AI video) / **FAIL** without ffmpeg. New pure `build_clip_command()`.
- New **`VideoProviderSettings`** config section (`AIVF_VIDEO_PROVIDER__PROVIDER|MODEL|TIMEOUT|RETRY_COUNT`), **separate** from the ffmpeg `VideoSettings` (`AIVF_VIDEO__*`). `.env.example` updated.
- New **CLI group `video`**: `video providers`, `video doctor`, `video generate --scene output/movie_consistent.json` (per-scene status table, continue-past-failure, non-zero exit if any scene failed).
- **Backward compatible & isolated**: `ffmpeg_command.py`, `FfmpegVideoComposer`, `compose` and every existing command are unchanged; only `app.py` and `settings.py` were modified.
- ADR-027 recorded. Tests: **52 new** (registry, mock provider, configuration, CLI) — ffmpeg is never invoked. **463 pass.**
- Verified against the real `movie_consistent.json`: 10 scenes → 10 requests (9:16 derived from 1080x1920; Sprint 019 character prompts and camera carried through) → correct ffmpeg argv → `completed` result. **A real render is still unverified — ffmpeg is not installed on this machine** (same blocker as Sprint 017).

### What was accomplished in the previous session (Sprint 019)
- New **domain models** `domain/value_objects/character_library.py`: `CharacterLibrary`, `CharacterProfile`, `NormalizedAppearance` (hair/eyes/face/body), `NormalizedOutfit` (clothes/accessories) — frozen Pydantic, matching the `output/character_library.json` schema exactly (`id, master_prompt, negative_prompt, seed, reference_image, appearance, outfit, voice_profile, version`).
- New **`infrastructure/character/`** package — **deterministic and offline, no AI provider**:
  - `CharacterConsistencyService.build(movie) -> CharacterLibrary`: normalizes traits, composes **one `master_prompt` per character** (fixed trait order + consistency clause), merges base + per-character **negative prompt**, derives the **seed from SHA-256(character id)**, and **merges duplicate character records** (first occurrence wins; a later record may only fill empty traits and add negatives).
  - `CharacterPromptInjector.inject(movie) -> Movie`: rewrites each scene's `image_prompt`/`video_prompt` as `<master prompts> | <original prompt> | negative: <terms>`. **Idempotent**; scenes without characters are untouched; an unknown character id raises `CharacterLibraryError`.
  - `reader.py` (`read_movie`, `read_character_library`), `writer.py`, `errors.py`.
- New **CLI group `character`**: `character build --input output/movie.json` → `output/character_library.json`; `character inject --movie output/movie.json [--library <path>]` → `output/movie_consistent.json` (a full, schema-valid `Movie`).
- **Additive & isolated**: the Movie Builder, image provider, TTS and compose were **not** modified; `movie.json` is never mutated. Only `app.py` changed (registers `character`).
- ADR-026 recorded. Tests: **37 new** (library models + JSON schema, normalization, seed generation, prompt generation, duplicate merge, injection, CLI). **411 pass.**
- Verified live on the real `movie.json`: 4 profiles with distinct deterministic seeds, duplicate-free; 10/10 scenes injected; originals preserved; source file unchanged.

### Current in-flight work
- None. Sprint 026 (second spec, Shot Planner) complete and verified live; Sprint 026 (first spec, Cinematic Director) complete but superseded; Sprint 025C complete and verified live; Sprint 025B complete and verified live; Sprint 025 complete; both Sprint 024 specs complete; Sprint 023 complete (unit-verified + stub-verified on real data; **live API still blocked by quota**); Sprint 022B complete (unit-tested; **no successful live run — the key is rate-limited, see risks**); Sprint 022A superseded in part; Sprint 022 complete and verified live; Sprint 021A complete; Sprint 021 complete (live Kling API still unverified — see below); Sprints 019–020 complete.

### Next Action (do this first)
> **Regenerate the images from the new prompts and look at them.** `output/shot_image_prompts.json` now holds the planned prompts (56.7% wide/full body, 3.3% close). The plan is verified on paper; whether the pictures actually stop being portraits can only be judged by looking. Run `ai-video-factory character memory --storyboard output/storyboard.json` **first** to fold the frozen identity back in - `shot-plan` rewrote the file it shares with Sprint 025C - then generate.
>
> Note the `image` stage still reads `image_prompts.json` (6 old scene prompts), so pointing it at `shot_image_prompts.json` is still the open wiring task from Sprint 025B.
>
> **Then: re-run the director once the Gemini quota resets, and fix `DIRECTOR_MODEL`.** `.env` sets `AIVF_PROVIDER__DIRECTOR_MODEL=gemini-2.5-flash`, which returns **404 NOT_FOUND — "no longer available to new users"** on this key (the same problem the transcription stage hit; it uses `gemini-flash-latest`). Either set a model this key can serve or clear the value to fall back to `AIVF_PROVIDER__MODEL`. Then `ai-video-factory director --movie output/movie_consistent.json`, and `--resume` if any scene fails.
>
> **Then: validate the Kling driver against the live API, cheaply.** Set `AIVF_VIDEO_PROVIDER__PROVIDER=kling`, `AIVF_VIDEO_PROVIDER__API_KEY=<Kling JWT>` and your `COST_PER_SECOND` rate, then:
> 1. `ai-video-factory video generate --dry-run` (spends nothing, needs no key — confirms the plan),
> 2. `ai-video-factory video doctor` (confirms the key is picked up),
> 3. `ai-video-factory video generate --limit 1` and answer `y` — **one paid job** against the real API.
>
> If the payload or response shape differs, the fix is localized to `kling/client.py` (or just the `BASE_URL`/`MODEL` settings). Then wait for the next Sprint spec. **Do NOT integrate Veo, Runway or Hailuo** — only Kling was approved.

### Context needed to continue
- **Default image provider is now `pollinations`** (`AIVF_IMAGE_PROVIDER__PROVIDER`, model `flux`) — free, no key. Switch to Gemini with `AIVF_IMAGE_PROVIDER__PROVIDER=gemini_imagen` + a key + a Gemini image model. Both go through `ImageProviderFactory` (drivers: `pollinations`, `gemini_imagen`).
- **Pollinations provider:** `providers/image/pollinations/{client,provider}.py`. `RealPollinationsClient` does `GET image.pollinations.ai/prompt/{prompt}?model&width&height&seed&nologo` (returns image bytes) and `GET /models`. Tested with httpx `MockTransport` (no network). No key needed → always builds a live client (no WARN-no-key path).
- **`image` flow (now):** if `output/images/001.png` exists and no `--force` → skip. Else `read_image_prompts` → `ImageProviderFactory.create` (storage uses `prefix=""` → `001.png`) → per-prompt `generate` (retries transient errors 3×) with a progress bar → `write_images_manifest` → `manifest.json` + summary.
- **Image retry is 3** by default (`AIVF_IMAGE_PROVIDER__RETRY_COUNT`); this also applies to the asset pipeline's image generator.
- **`ImageStorage` prefix:** default `"image"` (→ `image_001.png`, used by the asset pipeline) vs `""` (→ `001.png`, used only by the `image` CLI). Do not change the default — the asset-pipeline test asserts `image_001.png`.
- **`tts` flow:** `tts --input output/chapter.json` (alias `--chapter`). If `output/audio/narration.mp3` exists and no `--force` → skip. Else `read_chapter` → `SpeechProviderFactory.create` → `synthesize` (retries 3×) → save + `metadata.json`. `_ensure_utf8_stdout()` runs first (legacy-Windows cp1252 safety for the spinner + Vietnamese text).
- **Speech retry is 3** by default (`AIVF_SPEECH_PROVIDER__RETRY_COUNT`); this also applies to the asset pipeline's `SpeechAssetGenerator`.
- **`subtitle` flow:** `subtitle --audio output/audio/narration.mp3 --chapter output/chapter.json` (default `--language vi`). If `output/subtitles/narration.srt` exists and no `--force` → skip. Else check audio exists → `read_chapter` (reference text) → `TranscriptionProviderFactory.create` → `transcribe` (retries 3×) → `to_srt` → `SubtitleStorage.save` (UTF-8). Provider returns segments; the CLI writes the `.srt`.
- **Transcription provider:** `providers/transcription/` — driver `gemini_transcription`, default model **`gemini-flash-latest`** (audio-capable; `gemini-2.5-flash` 404s "not available to new users" on this key), retry 3 (`AIVF_TRANSCRIPTION_PROVIDER__RETRY_COUNT`), api-key falls back to the LLM key. Timing = Gemini ASR timestamps (best-effort; drifts somewhat).
- **`compose` flow:** `compose --images output/images --audio output/audio/narration.mp3 --subtitle output/subtitles/narration.srt`. Verifies ffmpeg via `check_ffmpeg()` (exit 1 + install message if absent) → validates inputs exist → `FfmpegVideoComposer(settings.video, output/video/final.mp4)` → `compose_video` builds argv (`build_ffmpeg_command`), runs off-loop with retry-once → `write_video_metadata` (`final.mp4` + `metadata.json`). Reads assets only; never regenerates.
- **Video composer:** `infrastructure/video/` — `FfmpegVideoComposer` implements the existing `VideoComposer` protocol; **injectable runner** (`default_ffmpeg_runner`) so tests mock ffmpeg. `VideoSettings` (`AIVF_VIDEO__*`): 1080x1920, 30fps, libx264/aac, fade 0.5s, retry_count 1. **ffmpeg must be on PATH** for a real render (not installed on this machine).
- **Two orchestrators:** `PipelineRunner` (story phase) and `AssetPipelineRunner` (media phase; images/voice ready, subtitle/video pending — the standalone `subtitle`/`compose` CLIs are separate from the asset pipeline's `SubtitleGenerator`/`VideoComposer` contracts, still unwired).
- **To wire video into the pipeline (future):** inject `FfmpegVideoComposer` into `AssetPipelineRunner` for the `compose_video` stage (it already satisfies the `VideoComposer` protocol) — no new adapter needed.
- **`movie` flow:** `movie --input output/chapter.json [--style cinematic --genre "" --language vi]`. `read_chapter` → `MovieBuilder.from_settings` (LLM JSON mode via `ProviderFactory`) → `parse_movie` (dedup characters by id = **fixed appearance**; inject style/genre/duration; retry-once) → `movie_writer.write_movie_json` → `output/movie.json`. Domain: `domain/value_objects/movie.py` (`Movie/Character/Appearance/Location/Camera/Scene`). Additive stage: Topic → Idea → Outline → Chapter → **Movie** (not yet wired into `PipelineRunner`).
- **`character` flow:** `character build --input output/movie.json` → `read_movie` → `CharacterConsistencyService().build` → `write_character_library_json` → `output/character_library.json`. Then `character inject --movie output/movie.json` → `read_movie` + `read_character_library` (default `output/character_library.json`, override with `--library`) → `CharacterPromptInjector(library).inject` → `output/movie_consistent.json`. **Both are pure/offline — no LLM, no network**, so tests need no mocks and runs are reproducible.
- **Consistency mechanism:** the seed is `SHA-256(character_id)` (case/space-insensitive) mod `2**31` — change the id and the seed changes. `master_prompt` trait order is fixed (name, gender, age, hair, eyes, face, body, wearing …, accessories, consistency clause); empty traits are omitted. `BASE_NEGATIVE_TERMS` in `character/service.py` are the shared negatives.
- **Injected prompt format:** `<master prompts> | <original prompt> | negative: <terms>` (`SEPARATOR = " | "`, `NEGATIVE_MARKER = "negative:"` in `character/injector.py`). `_strip()` recovers the original prompt, which is what makes injection idempotent — keep it in sync if the format ever changes.
- **`movie_consistent.json` is not yet wired into image generation** — the `image` command still reads `output/image_prompts.json`. Pointing a media stage at the consistent movie is a future sprint's call.
- **`video` flow:** `video providers` (list + configured default), `video doctor` (health per driver; **exit 1 only if the *configured* provider FAILs**), `video generate --movie output/movie_consistent.json` (`--scene` alias, `--images` override) → `read_scene_movie` + `build_requests(images_dir=…)` → `build_default_registry(on_progress=…).create_default` → `health_check` gate (exit 1 if FAIL) → per-scene `generate` with continue-past-failure → `write_video_manifest` → summary table → `output/video_clips/scene_NNN.mp4` + `manifest.json`.
- **Video provider layer:** `infrastructure/video/providers/` — `base/{models,provider,writer}.py`, `registry.py`, `mock/{clip_command,provider}.py`, `kling/{client,models,provider}.py`, `scene_reader.py`, `errors.py`. Registered drivers: **`mock`** (default, local ffmpeg) and **`kling`**. Adding another = satisfy the `VideoProvider` protocol + register a builder in `build_default_registry()`.
- **Kling driver:** async submit→poll→download. `client.py` is the only HTTP module (seam: `KlingClient`); `build_submit_payload`/`parse_job` are pure. Auth = `Authorization: Bearer <API_KEY>` (Kling mints that JWT from an ak/sk pair). Downloads deliberately go **unauthenticated** so the key never reaches the CDN. `poll_timeout` overrun → the job is **cancelled** then the error raised. Unknown `task_status` → RUNNING (never a discarded job).
- **Kling is UNVERIFIED against the live API** — endpoint shapes come from Kling's published docs; only a local stub server has exercised them. Cancellation (`DELETE`) is the least certain endpoint; it is used only on poll timeout, where failure is logged and swallowed.
- **`director` flow:** `director --movie output/movie_consistent.json [--library output/character_library.json]` → `read_movie` + `read_optional_library` → `DirectorService.from_settings` (LLM JSON mode via `ProviderFactory`) → `direct()` = `_plan()` (one LLM call, **retry once**) then `apply()` (pure) → `write_directed_movie_json` → `output/movie_directed.json`. Domain: `domain/value_objects/director.py`. The library is **optional** — without it the prompt carries camera and motion language only, and the CLI says so.
- **Director design:** the shot plan is LLM-generated (motion fields require reading scene content); `build_director_prompt()` is **pure and deterministic**, so `apply()` is reproducible for a given plan. Empty fields are **omitted, never padded**. `derive_notes()` fills gaps only from `Scene.camera`/`action`/`emotion` + `Movie.style`.
- **Do not let the director re-describe characters** — `prompts/director/shot_plan.md` forbids it, and that instruction is what keeps Sprint 019's consistency intact. A test asserts the phrase "identity is fixed elsewhere" is in the rendered prompt.
- **`movie_directed.json` is a superset of `movie.json`** (`DirectedScene`/`DirectedMovie` subclass `Scene`/`Movie`), so it validates as a plain `Movie` and any existing reader works unchanged. **Nothing consumes `director_prompt` yet** — pointing the video stage at it is a future sprint's call.
- **Cost guard:** `video generate` takes `--dry-run` (preview only, no provider built, no credentials needed), `--limit N` (first N scenes), and `--yes` (skip the prompt). Any provider but `mock` prompts before submitting; the prompt defaults to **No** and a non-interactive stream declines. Declining exits **0**. `GenerationPlan` (`video/providers/cost.py`) backs both the preview and the manifest estimates.
- **Cost is an estimate:** Kling returns no price. The manifest records `estimated_cost` (projected) and `actual_cost` (`duration × AIVF_VIDEO_PROVIDER__COST_PER_SECOND`; `0.0` for a failed scene). Both `0.0` means *unknown/unconfigured* — **not free**.
- **Manifest field names changed in Sprint 021A** — `cost`/`total_cost` are gone. Any pre-021A `output/video_clips/manifest.json` on disk is in the old shape; it is a regenerated artifact, so just re-run rather than migrating.
- **Scene→image matching is by position**, not `scene.id`: the Nth scene uses `output/images/{N:03d}.png`. A missing image fails that scene for Kling (image-to-video needs one) but falls back to a colour card for `mock`.
- **Two separate video config sections — do not conflate:** `AIVF_VIDEO__*` (`VideoSettings`) is the **ffmpeg composition** config used by `compose` *and* by the mock provider's rendering; `AIVF_VIDEO_PROVIDER__*` (`VideoProviderSettings`: provider/model/timeout/retry_count) selects the **AI video driver**.
- **Mock provider caveat:** it renders slideshow clips with local ffmpeg, **not AI video** — hence its health is deliberately `WARN`, never `OK`. It needs ffmpeg on PATH, so `video doctor`/`video generate` currently FAIL on this machine (same blocker as `compose`).
- **`_strip`/registry note:** `build_default_registry()` returns a **fresh** registry each call (no global mutable state); registering a fake in a test cannot leak into another test.
- **Testing:** inject a fake `LLMProvider`/`SpeechProvider`/ffmpeg runner; `asyncio.run`; no real API. The skip test needs no mock (skip returns before building the provider). Movie tests use `FakeProvider` + the real `prompts/story/movie.md` template. Character tests need no fakes at all (the stage is deterministic). Video tests patch `mock.provider.check_ffmpeg` and `mock.provider.default_ffmpeg_runner` (the runner is resolved at construction, not as a default argument, precisely so it stays patchable).
- **Tooling:** `uv`; `make lint/format/typecheck/test`. Console script `ai-video-factory`.

### Decisions made this session
- Added ADR-038 - **Character Memory Engine**.
- **The canon is frozen, not re-derived**: a look that changes between runs is the drift the stage exists to stop.
- **An adopted reference is never re-pointed** - that would redefine the character mid-film.
- **Adoption by existence, not by hooking image generation** - hooking the `image` command would modify a stage outside this sprint's remit for the same end state.
- **Unrecorded attributes score 0**, marked `(not remembered)` - the same honesty rule as ADR-037's scorer.
- **Provider capability is a set, not a hardcode**: adding a reference-capable driver to `PROVIDERS_WITH_IMAGE_REFERENCE` attaches the path instead of describing it.
- Added ADR-037 - **Visual Continuity Engine**.
- **Asked before building** on the two spec gaps (missing bibles; `image_prompts.json` ownership) rather than guessing.
- **Bibles are derived then hand-editable** - reproducible by default, enrichable where it matters.
- **Continuity only within a scene**: asserting it across a cut would fight the story.
- **Regeneration escalates explicitness** so a retry changes the text; when the cause is missing data it is reported, not looped.
- **Absent source data counts against the score.** Excusing it produced a scorer that always said 100 - I caught that and rewrote it.
- Added ADR-036 - **AI video generation from the storyboard**.
- **Asked the Lead before building** rather than guessing on two spec conflicts (portrait vs landscape; 4-8s clips vs 2-5s shots). Both answers are recorded in the ADR.
- **Merging over stretching**: shot durations are never rewritten, so the 90s timeline survives intact.
- **Scene boundaries beat the duration floor**: a short clip is better than a clip containing a hard cut. The shortfall is reported, not hidden.
- **References are offered, not required**: `generate(request, references)` lets a provider ignore what it cannot use.
- Added ADR-034 (**OpenRouter as the director's provider**) and ADR-035 (**Storyboard Builder**).
- **Honoured the flat env names verbatim** (`AIVF_OPENROUTER_API_KEY`, not `AIVF_OPENROUTER__API_KEY`) - they were specified explicitly; `Settings.openrouter` keeps call sites typed.
- **The director selects its provider independently** of the story pipeline, so switching it cannot disturb idea/outline/chapter generation.
- **The storyboard never rewrites shot durations** to fit the narration - that would break the director's 2-5s rule; drift is reported instead.
- **Subtitles are mapped by overlap, not containment**, so a cue spanning a shot boundary appears on both shots it is heard over.
- Added ADR-033 — **Batch Director + Shot Planner**. A video model renders a *shot*, not a scene, so the plan is now per shot.
- **Removed `DirectorNotes`/`director_prompt` rather than keeping them beside `shots`** — nothing would populate them, and CLAUDE.md forbids dead code.
- **The 3-8 / 2-5s rules conflict for short scenes**; resolved by capping the shot count at what the scene's length allows rather than failing the scene over arithmetic it cannot satisfy.
- **The parser repairs deterministically** (renumber, clamp, trim) but never invents: structural failures are reported.
- Added ADR-032 — **one request plans the whole movie**, superseding ADR-031 §1–2. Cost and rate-limit pressure beat per-scene failure granularity.
- **The character library goes into the prompt as ids + voice notes only** — sending the master prompts would invite the director to re-describe characters, which is exactly what ADR-026 forbids.
- **An unparseable answer re-asks the whole question** (3 attempts) rather than failing the run outright; an omitted scene is *not* chased with an extra call — `--resume` handles it.
- Added ADR-031 (previous session) — **Director Provider Resilience**.
- **One call per scene** — independent per-scene retry is impossible with a bulk call. Accepted cost: ~10× the requests for a ten-scene movie.
- **Jitter and the retry hook are opt-in on the shared `RetryPolicy`** (`jitter=0.0` default) so no existing provider's timing changed.
- **A failed scene gets no fallback notes** — plausible-looking filler would be indistinguishable from success and `--resume` could never find it.
- **Parse failures are terminal for that scene**; the retry budget belongs to transport failures, since re-sending identical input rarely yields different JSON.
- Added ADR-030 (previous session) — **AI Director**. New stage between consistency and video generation.
- **Subclassed rather than extended**: `DirectedScene(Scene)` / `DirectedMovie(Movie)` keep `movie.py` untouched, so the Movie Builder's schema and tests are unaffected and the directed document still reads as a `Movie`.
- **LLM for the plan, pure code for the prompt**: motion fields can't be derived mechanically without producing filler; prompt assembly stays deterministic and testable.
- **Empty fields are omitted, not padded** — inventing "natural movement" would recreate the generic prompts this stage exists to replace.
- **The director never rewrites `video_prompt`** — destroying the original would make the stage irreversible and unauditable.
- Added ADR-029 (previous session) — **Cost Guard**. Spending requires an interactive "y" or an explicit `--yes`.
- **The prompt defaults to No and a non-interactive stream declines** — the safe direction for a money-spending command is "don't".
- **Declining exits 0**, not 1: the user chose it; nothing failed.
- **`--dry-run` builds no provider** so it works without credentials — a preview that fails for want of a key is useless precisely when you need it.
- **`cost` was split into `estimated_cost` + `actual_cost`** rather than adding a third field; three overlapping cost fields is the ambiguity this removes. Breaking, but the manifest is a regenerated artifact.
- Added ADR-028 (previous session) — **Kling AI Video Provider**. First real video driver, behind the Sprint 020 contract.
- **`mock` stays the default driver** — Kling needs a paid key, and flipping the default would break `video generate`/`video doctor` for anyone without credentials.
- **No Kling-specific settings section**: reused the existing `VIDEO_PROVIDER` fields (`api_key`/`base_url`/`model`) and added `poll_interval`/`poll_timeout`/`cost_per_second`. Per-vendor sections would multiply with every driver.
- **`poll_timeout` is separate from `timeout`**: one bounds the whole remote render, the other one HTTP request. An overrun **cancels** the job rather than abandoning it while it bills.
- **Cost is reported as an estimate from a configured rate, `0.0` = unknown** — fabricating a price would be worse than admitting we don't have one.
- **`video doctor` now judges only the configured provider** — adding a second driver made the previous "any FAIL fails the command" rule wrong.
- Added ADR-027 (previous session) — **AI Video Provider Layer (abstraction only)**. **No commercial provider integrated**, per the sprint's strict rule.
- **Placement deviation (deliberate, documented):** the layer lives at `infrastructure/video/providers/` because the sprint named `infrastructure/video/`; every other provider layer lives at `infrastructure/providers/<capability>/`. One documented deviation beat splitting video concerns across two trees. Revisit only on the Lead's word.
- **Protocol, not ABC** — matches the image/speech/transcription layers; a driver satisfies the contract structurally without importing a base class.
- **Registry is constructed, not module-global** (`build_default_registry()`), honouring the no-global-mutable-state rule.
- **`VIDEO_PROVIDER` is its own settings section**, separate from the ffmpeg `VideoSettings`, so the compose stage's config is untouched.
- **`QUEUED`/`RUNNING`, `remote_job_id`, `preview_path`** are unused by local providers on purpose — an asynchronous remote driver will need no model change.
- Added ADR-026 (previous session) — **Character Consistency Engine**. The stage is **deterministic and offline**: master prompts are composed from the movie bible's structured traits rather than generated by the LLM, because an LLM would drift between runs and defeat the purpose.
- **Appearance vs outfit split**: `NormalizedAppearance` (hair/eyes/face/body) is the permanent identity; `NormalizedOutfit` (clothes/accessories) is the wardrobe — so a costume change can never be read as an identity change.
- **Duplicate merge is first-wins**, consistent with ADR-025; a later record may only fill traits the first left empty and contribute negative terms.
- **Injection preserves the original prompt and is idempotent**; a scene referencing an unknown character id fails loudly rather than silently rendering an undescribed character.
- **Additive only**: touched no existing generator/image/TTS/compose; `movie.json` is never mutated; the new stage is not wired into `PipelineRunner` or the image stage (kept isolated).

### Open questions / risks for next session
- **Three commands now write `shot_image_prompts.json`** - `continuity`, `cinema` and `shot-plan`. `shot-plan` is the intended producer (ADR-040); the others are earlier stages of the same idea. The last one run wins, and nothing enforces an order. A single owned pipeline command would fix this properly and is worth a sprint.
- **The upstream storyboard is still tight-framed** (9 close-ups, 9 mediums of 30). The planner overrules it, but the director would produce better raw material if asked for varied coverage - fixing it at the source would mean the plan had less to correct.
- **The plan is verified on paper, not in pictures.** 56.7% wide/full body means the prompts ask for wide shots; whether the model obeys can only be judged by generating and looking.
- **`output/shot_image_prompts.pre026.bak` and `.pre-shotplan.bak` are my own backups** taken before each rewrite. Safe to delete once the new prompts are confirmed good - neither is a user artifact.
- **`cinema` and `character memory` share `shot_image_prompts.json`.** Running `cinema` replaces the continuity engine's prompts, so the frozen-identity block from Sprint 025C is dropped - re-run `ai-video-factory character memory --storyboard output/storyboard.json` afterwards to restore it. The CLI warns, but nothing enforces the order; a single owned pipeline command would.
- **`output/shot_image_prompts.pre026.bak` is my own backup** taken before the first `cinema` run. Safe to delete once the current prompts are confirmed good - it is not a user artifact.
- **The direction is judged by the shot list, not by pictures.** Varied coverage on paper is not the same as a film that reads well; that needs generated images to assess.
- **Only `diep_pham` has a reference image.** `output/images/` holds six stills generated from the *old* per-scene prompts, so only shots 1-6 map to files. The other three characters adopt a reference as soon as an image exists for one of their shots.
- **`weapon (not remembered)` is the standing deduction** for characters whose bible records no weapon - fix by editing `character_bible.json` or `character_memory.json` directly; both survive reruns.
- **No image driver accepts a reference image**, so identity travels as words. Wiring image-to-image on Pollinations or Imagen is a provider change and needs its own sprint; when it lands, add the driver to `PROVIDERS_WITH_IMAGE_REFERENCE`.
- **The score measures the prompt, not the picture.** 97 means the prompts pin the identity; whether the generated images actually match can only be judged by looking at them.
- **Nothing regenerates images yet.** `shot_image_prompts.json` is now fully enriched but the `image` stage still reads `image_prompts.json`; wiring it is still open from Sprint 025B.
- **Nothing consumes `shot_image_prompts.json` yet.** The `image` stage still reads `image_prompts.json` (6 scene prompts). Repointing it is a later sprint's call - and note that doing so makes `output/images/` per-shot, which the video stage's `images/{scene_id}.png` lookup does not expect.
- **The derived world bible is thin**: no era, no weather, no motifs, because nothing upstream records them. That is why `weather` and `props` are the standing score deductions. Hand-editing `world_bible.json` is the intended fix and survives reruns.
- **The scorer measures prompt *coverage*, not image output.** A 93 means the prompt states what it should, not that the generated images actually match - that can only be judged by looking at them.
- **10 of 20 clips from the real storyboard are 3s**, under the 4s floor: a 9s scene of three 3s shots cannot split evenly without crossing a cut. The fix is upstream - longer shots from `director` (e.g. 4-5s), which would also reduce the clip count.
- **Character reference images are never populated.** `CharacterProfile.reference_image` has been `None` since Sprint 019, so `ClipReferences.character` is always empty and identity reaches the provider through prompt text only. Wiring generated character stills into the library would close the loop.
- **Clip files were renamed `scene_NNN.mp4` -> `shot_NNN.mp4`.** Earlier runs left `scene_*.mp4` in `output/video_clips/`; they are untouched and now orphaned. Delete them when convenient - I did not, since I did not create them.
- **Clips render at 30fps** (`VideoSettings.fps`), not the 24 the spec mentioned; the Lead's choice to match `VideoSettings` for the frame made this consistent. `AIVF_VIDEO__FPS=24` changes it.
- **No live AI-provider render.** The mock needs ffmpeg (absent from this shell) and Kling needs credentials. The whole path is unit-tested and the plan verified against the real storyboard.
- **`output/subtitles/narration.srt` is mistimed**: it spans 109.5s while `narration.mp3` is 66.7s. Every storyboard subtitle is therefore misplaced, and compose would burn in the same bad timings. Re-run `subtitle` (the transcription stage's ASR timestamps drift - already noted in Known Issues).
- **The live OpenRouter API is unverified** - no credentials were available. Endpoint shapes follow OpenRouter's published OpenAI-compatible contract; every test uses `httpx.MockTransport`. Set `AIVF_OPENROUTER_API_KEY` and run `director` to confirm.
- **The shot timeline (90.0s) exceeds the narration (66.7s) by 23.3s** on the real movie. Nothing reconciles them yet - a future stage must decide whether to trim shots, extend narration, or accept silence.
- **Two specs shared the number 024.** They are recorded as ADR-034 and ADR-035; the next sprint number is **025**.
- **Sprint 023 has no live-API run** — the Gemini key is quota-exhausted. Behaviour is proven by unit tests and by a stubbed end-to-end run against the real `movie_consistent.json` (1 request, 30 shots, bounds respected). Re-run when quota resets.
- **`movie_directed.json` on disk is still the Sprint 022 shape** (`director`/`director_prompt`). Regenerate it with `director`; the old file will not validate as the new schema.
- **Nothing consumes `shots` yet** — the Kling driver still sends `scene.video_prompt`. Wiring the video stage to per-shot prompts is the obvious next step and would change clip granularity from scene to shot.
- **The Gemini key is quota-exhausted (429).** Every live director attempt this session ended in 429 after full backoff, so **Sprint 022B has no successful live run** either. The single-call behaviour is proven by unit tests (`provider.calls == 1`), not by a live render. Re-run when quota resets.
- **SDK-level retry multiplies ours** (~4×). If rate limits stay painful, consider configuring the `google-genai` client's own retry/timeouts in `RealGeminiClient` so the two layers do not compound.
- **`RetryPolicy` ignores a `retry_after` hint larger than `max_delay`** — Gemini asked 51s, we waited 16.5s. Recommend honouring the hint above the cap; not done here because it changes behaviour for every provider.
- **Sprint 022A's per-scene note is now historical.** The unit tests cover every required behaviour, and the resilience machinery was observed working against the real API (backoff, per-scene retry, isolation, clean report, partial handling). But no run completed: first `DIRECTOR_MODEL=gemini-2.5-flash` returned **404 NOT_FOUND**, then the key hit **429 rate limit / quota** — which per-scene planning reaches ~10× faster than the old bulk call. **Re-run when quota resets to confirm end-to-end.**
- **`AIVF_PROVIDER__DIRECTOR_MODEL=gemini-2.5-flash` in `.env` is invalid for this key** ("no longer available to new users"). Set a servable model or clear it to fall back to `AIVF_PROVIDER__MODEL`. The code default in `settings.py` has the same value and the same problem.
- **Per-scene planning costs ~10× the requests.** For a ten-scene movie that is ten calls per run instead of one — materially more quota and wall-clock. Worth revisiting if quota is tight (e.g. batching a few scenes per call while keeping per-batch retry).
- **Some scenes returned unparseable JSON** during the live attempt ("director returned …"). Parse failures are terminal per scene by design, so those scenes simply fail and `--resume` retries them — but if it proves common, the per-scene prompt may need tightening.
- **I destroyed two output files during this session** (see "Files touched"): a newer `movie_directed.json` and a partial were overwritten/removed while restoring a backup. `output/` is gitignored, so they are unrecoverable. Regenerate with `director` once the model/quota issues are resolved.
- **`director_prompt` is produced but nothing consumes it.** The Kling driver still sends `scene.video_prompt`; wiring the video stage to `director_prompt` (and reading `movie_directed.json` rather than `movie_consistent.json`) is the obvious next step — deliberately out of Sprint 022's scope.
- **The shot plan is non-deterministic** (LLM-generated), unlike the character library. Re-running `director` yields a different plan; `apply()` is deterministic only for a *given* plan. If reproducibility matters, keep `movie_directed.json` rather than regenerating it.
- **The live Kling API has never been called.** No credentials were available, so the payload/response/cancel shapes are from documentation only. Highest-risk items, in order: the cancel endpoint (least documented), the auth header form, and the `duration` field's type (sent as a string). All are localized to `kling/client.py`.
- **Kling still has no cost *ceiling*.** Sprint 021A added preview, cap and confirmation, but nothing aborts a run mid-way once confirmed — that would need per-job cost reporting Kling does not provide. A confirmed 10-scene run spends the full estimate.
- **`ffmpeg` may now be installed.** `output/video_clips/` holds ten genuine ffmpeg-encoded MP4s (mock provider, old-format manifest) that this session did not create — so the mock render path evidently works end-to-end on this machine. ffmpeg was not visible on `PATH` from this session's shells (stale environment), so `doctor` still reports FAIL here. **Re-check `factory doctor` in a fresh terminal** before trusting the "ffmpeg missing" note elsewhere in this document.
- **No real render has ever been verified** — ffmpeg is still not installed on this machine, so `compose` (Sprint 017), `video doctor` and `video generate` all exit 1 with the install message. The argv and the whole request/result flow are verified against real data and unit-tested; the pixels are not. Operator action: install ffmpeg.
- **`VideoGenerationRequest.negative_prompt` is left empty** by `scene_reader`: the Sprint 019 injector embeds the negatives *inside* the scene prompt (`… | negative: …`). Splitting them back out would couple the video package to `character/injector.py`'s format constants, so it was deliberately deferred. A provider that wants a separate negative prompt will need that decision made.
- **`reference_images` is always empty** today — generated images are not yet associated with scenes, so the mock renders colour cards. Wiring `output/images/NNN.png` to scenes is a future task.
- `movie_consistent.json` is produced but **nothing consumes it yet** — wiring the image stage to it is a future task (deliberately out of Sprint 019's scope).
- The master prompt inherits whatever detail the Movie Builder produced; a sparse `movie.json` yields a sparse master prompt. Consistency is enforced structurally (same prompt + same seed), not by validating trait richness.
- Seed reuse across scenes gives consistency but can also reduce composition variety — worth watching once images are regenerated from the injected prompts.
- Movie Builder is a standalone CLI stage; wiring it into `generate`/`PipelineRunner` (Chapter → Movie) is a future task.
- **Live ffmpeg render (Sprint 017) still pending** an ffmpeg install by the operator.

### Files touched this session
- New source: `domain/value_objects/shot_plan.py`; `infrastructure/planner/{__init__,classifier,framing,environment,distribution,planner,prompt_composer,statistics,engine,reader,errors}.py`; `interface/cli/planner_commands.py`; `interface/presenters/planner_presenter.py`.
- Modified source: `interface/cli/app.py` (registers `shot-plan`) - **only** file changed. Providers, video, compose, storyboard, director, the continuity engine and the cinema module all untouched.
- Tests: new `test_shot_planner.py` (51), `test_shot_plan_cli.py` (13).
- Docs: `04_DECISIONS.md` (ADR-040, ADR-039 marked superseded), `12_PROJECT_STATE.md`, `13_SESSION_HANDOFF.md`, `CHANGELOG.md`.
- Earlier this session (Sprint 026 first spec) new source: `domain/value_objects/cinema.py`; `infrastructure/cinema/{__init__,vocabulary,scene_director,shot_director,engine,reader,errors}.py`; `interface/cli/cinema_commands.py`; `interface/presenters/cinema_presenter.py`.
- Modified source: `infrastructure/continuity/prompt_composer.py` (rewritten to the director's order; `direction` optional), `interface/cli/app.py` (registers `cinema`). Providers, video, compose, storyboard, director and the memory engine untouched.
- Tests: new `test_cinema_director.py` (36).
- Docs: `04_DECISIONS.md` (ADR-039), `12_PROJECT_STATE.md`, `13_SESSION_HANDOFF.md`, `CHANGELOG.md`.
- Previous session (Sprint 025C) new source: `domain/value_objects/character_memory.py`; `infrastructure/memory/{__init__,builder,validator,enricher,engine,reader,errors}.py`; `interface/cli/memory_commands.py`; `interface/presenters/memory_presenter.py`.
- Modified source: `interface/cli/character_commands.py` (registers `character memory`) - **only** file changed. Providers, video, compose, storyboard, director and the continuity engine untouched.
- Tests: new `test_character_memory.py`, `test_character_memory_cli.py`.
- Docs: `04_DECISIONS.md` (ADR-038), `12_PROJECT_STATE.md`, `13_SESSION_HANDOFF.md`, `CHANGELOG.md`.
- New source: `domain/value_objects/continuity.py`; `infrastructure/continuity/{__init__,bibles,context,prompt_composer,scorer,engine,reader,errors}.py`; `interface/cli/continuity_commands.py`; `interface/presenters/continuity_presenter.py`.
- Modified source: `interface/cli/app.py` (registers `continuity`) - **only** file changed. Providers, video stage, compose, storyboard and director untouched.
- Tests: new `test_continuity_engine.py`, `test_continuity_cli.py`.
- Docs: `04_DECISIONS.md` (ADR-037), `12_PROJECT_STATE.md`, `13_SESSION_HANDOFF.md`, `CHANGELOG.md`.
- New source: `infrastructure/video/providers/{clip_planner,storyboard_source}.py`.
- Modified source: `video/providers/base/models.py` (+`ClipReferences`, `clip_id`/`shot_ids`/`width`/`height`), `base/provider.py` (`generate(request, references)`), `base/writer.py` (manifest `clip_id`/`shot_ids`), `mock/provider.py` and `kling/provider.py` (references + clip naming), `scene_reader.py` (`clip_id` per scene), `interface/cli/video_commands.py` (`--storyboard`, `--resume`, references, short-clip warning). **Director, Storyboard and Compose untouched.**
- Tests: new `test_clip_planner.py`, `test_video_storyboard_cli.py`; updated `test_mock_video_provider.py`, `test_kling_provider.py`, `test_video_cli.py`, `test_video_cost_guard.py`, `test_video_kling_cli.py`, `test_video_manifest.py` for the rename and richer manifest.
- Docs: `04_DECISIONS.md` (ADR-036), `12_PROJECT_STATE.md`, `13_SESSION_HANDOFF.md`, `CHANGELOG.md`.
- New source: `infrastructure/providers/openrouter/{__init__,client,provider}.py`; `domain/value_objects/storyboard.py`; `infrastructure/storyboard/{__init__,builder,narration,reader,errors}.py`; `interface/cli/storyboard_commands.py`; `interface/presenters/storyboard_presenter.py`.
- Modified source: `infrastructure/config/settings.py` (+`OpenRouterSettings`, flat director/OpenRouter fields), `providers/factory/provider_factory.py` (+`create_director`, `director_model`, openrouter driver), `infrastructure/director/service.py` (uses `create_director`), `interface/cli/app.py` (registers `storyboard`). Compose, image generation, TTS and the video providers untouched.
- Config: `.env.example` (+director/OpenRouter block).
- Tests: new `test_openrouter_client.py`, `test_openrouter_provider.py`, `test_storyboard_builder.py`, `test_storyboard_cli.py`.
- Docs: `04_DECISIONS.md` (ADR-034, ADR-035), `12_PROJECT_STATE.md`, `13_SESSION_HANDOFF.md`, `CHANGELOG.md`.
- New source: `infrastructure/director/{shot_planner,shot_parser}.py`.
- Rewritten: `domain/value_objects/director.py` (`Shot`, `DirectedScene.shots`), `infrastructure/director/{service,prompt_builder,__init__}.py`, `prompts/director/shot_plan.md`, `interface/presenters/director_presenter.py`. **Removed** `infrastructure/director/notes_parser.py`.
- Tests: rewrote `test_director_models.py`, `test_director_prompt.py`; migrated `test_director_resilience.py`, `test_director_service.py`, `test_director_resume_cli.py`, `test_director_cli.py` to shots.
- Docs: `04_DECISIONS.md` (ADR-033), `12_PROJECT_STATE.md`, `13_SESSION_HANDOFF.md`, `CHANGELOG.md`.
- Untouched, as required: Movie Builder, Character Library, video providers, compose.
- Modified source: `infrastructure/director/service.py` (single-request planning, `_map`, parse-retry loop; per-scene machinery removed), `interface/cli/director_commands.py` (`_PlanProgress` replaces `_SceneProgress`), `prompts/director/shot_plan.md` (bulk prompt + cast + locations).
- Tests: rewrote `test_director_resilience.py` and `test_director_resume_cli.py` for single-request semantics; updated `test_director_service.py`.
- Docs: `04_DECISIONS.md` (ADR-032; ADR-031 marked partially superseded), `12_PROJECT_STATE.md`, `13_SESSION_HANDOFF.md`, `CHANGELOG.md`.
- Previous session (Sprint 022A): `infrastructure/director/report.py`.
- Modified source: `infrastructure/providers/base/retry.py` (**opt-in** `jitter`, `on_retry`, `rng` — defaults unchanged), `infrastructure/providers/gemini/client.py` (`map_transport_error` + `transport_error_types`, applied at all three SDK call sites), `infrastructure/director/service.py` (per-scene planning, retry, report, resume, `director_model`), `infrastructure/director/reader.py` (`read_optional_directed_movie`), `infrastructure/director/__init__.py`, `interface/cli/director_commands.py` (`--resume`, partial save, report), `interface/presenters/director_presenter.py` (`render_direction_report`), `prompts/director/shot_plan.md` (per-scene + previous-shot context).
- Tests: new `test_director_resilience.py`, `test_director_resume_cli.py`; updated `test_director_service.py` + `test_director_cli.py` for the `(movie, report)` signature.
- Docs: `04_DECISIONS.md` (ADR-031), `12_PROJECT_STATE.md`, `13_SESSION_HANDOFF.md`, `CHANGELOG.md`.
- **Data loss (my error):** while restoring a backup I overwrote `output/movie_directed.json` (a newer 70 KB version) with an older 65 KB copy, and deleted `output/movie_directed.partial.json`. `output/` is gitignored — both are gone. The current `movie_directed.json` is the Sprint 022 run (10 scenes, all with prompts) and is valid.
- Previous session (Sprint 022): `domain/value_objects/director.py`; `infrastructure/director/{__init__,service,prompt_builder,notes_parser,reader,errors}.py`; `interface/cli/director_commands.py`; `interface/presenters/director_presenter.py`; `prompts/director/shot_plan.md`.
- Modified source: `interface/cli/app.py` (register `director`) — **only** file changed. Movie Builder, Character Library, providers, image generation, TTS and compose untouched.
- Tests: new `test_director_models.py`, `test_director_prompt.py`, `test_director_service.py`, `test_director_cli.py`.
- Docs: `04_DECISIONS.md` (ADR-030), `12_PROJECT_STATE.md`, `13_SESSION_HANDOFF.md`, `CHANGELOG.md`.
- Previous session (Sprint 021A): `infrastructure/video/providers/cost.py`.
- Modified source: `video/providers/base/writer.py` (`estimated_cost`/`actual_cost`, `estimates=` param), `video/providers/__init__.py` (exports), `interface/cli/video_commands.py` (`--dry-run`/`--limit`/`--yes`, `_confirm_spend`), `interface/presenters/video_provider_presenter.py` (`render_generation_plan`). **No provider, compose, TTS or image code touched.**
- Tests: new `test_video_cost_guard.py`; updated `test_video_manifest.py` (new cost fields) and `test_video_kling_cli.py` (`--yes` on paid runs).
- Docs: `04_DECISIONS.md` (ADR-029), `12_PROJECT_STATE.md`, `13_SESSION_HANDOFF.md`, `CHANGELOG.md`.
- Previous session (Sprint 021): `infrastructure/video/providers/kling/{__init__,client,models,provider}.py`; `infrastructure/video/providers/base/writer.py`.
- Modified source: `infrastructure/config/settings.py` (+`base_url`/`poll_interval`/`poll_timeout`/`cost_per_second` on `VideoProviderSettings`), `video/providers/registry.py` (+`kling` driver, `on_progress` passthrough), `video/providers/scene_reader.py` (+optional `images_dir`), `video/providers/__init__.py` (exports), `interface/cli/video_commands.py` (`--movie`/`--images`, phase progress, manifest, doctor exit rule). **`compose`, TTS, image generation and the ffmpeg composer untouched.**
- Config: `.env.example` (+Kling block).
- Tests: new `test_kling_client.py`, `test_kling_provider.py`, `test_video_manifest.py`, `test_video_kling_cli.py`; updated `test_video_provider_registry.py` + `test_video_cli.py` (the Sprint 020 "no commercial provider" assertions now read "no *unapproved* provider").
- Docs: `04_DECISIONS.md` (ADR-028), `12_PROJECT_STATE.md`, `13_SESSION_HANDOFF.md`, `CHANGELOG.md`. Architecture doc (`ai-tool.md`) untouched.
- Previous session (Sprint 020): `infrastructure/video/providers/{__init__,errors,registry,scene_reader}.py`, `.../base/{__init__,models,provider}.py`, `.../mock/{__init__,clip_command,provider}.py`; `interface/cli/video_commands.py`; `interface/presenters/video_provider_presenter.py`.
- Modified source: `infrastructure/config/settings.py` (+`VideoProviderSettings`, +`video_provider` field) and `interface/cli/app.py` (register the `video` group) — **only** two files changed. `ffmpeg_command.py`, `ffmpeg_composer.py`, `writer.py` and every existing generator/image/TTS/compose module untouched.
- Config: `.env.example` (+`AIVF_VIDEO_PROVIDER__*` block).
- Tests: new `test_video_provider_registry.py`, `test_mock_video_provider.py`, `test_video_provider_settings.py`, `test_video_cli.py`.
- Docs: `04_DECISIONS.md` (ADR-027), `12_PROJECT_STATE.md`, `13_SESSION_HANDOFF.md`, `CHANGELOG.md`. Architecture doc (`ai-tool.md`) untouched.
- Previous session (Sprint 019): `domain/value_objects/character_library.py`; `infrastructure/character/*`; `interface/cli/character_commands.py`; `interface/presenters/character_presenter.py`; four `test_character_*.py` files.

### Do NOT do
- Do not add a Web UI, FastAPI, or Docker (ADR-001, ADR-004; non-goals).
- Do not put I/O or vendor code in `domain/`.
- **Do not integrate Veo, Runway, Hailuo, or any other video provider** — only Kling was approved (Sprint 021).
- Do not modify the Movie Builder, the image provider, the TTS stage, or the ffmpeg composer; do not regenerate images/audio/subtitles; do not wire `movie_consistent.json` into image generation, and do not compose the generated clips into the final MP4 — future sprints.
- Do not make `kling` the default driver without the Lead's word — it would break the CLI for anyone without a paid key.

---

## Handoff History (rolling, newest first)

### 2026-07-20 — Sprint 026 (second spec) Cinematic Shot Planner delivered
- Every frame is planned and the film is validated as a distribution (ADR-040), superseding ADR-039. New `shot-plan` CLI writes `shot_plan.json` + `shot_statistics.json` and rebuilds the prompts. Coverage follows what each scene is doing; close <=20% / medium 20-35% / wide >=40% / establishing >=5% is enforced with automatic re-planning; a frame stating nothing at any depth is rejected; portrait language is stripped from source text and refused in the negatives. Diagnosed the root cause first: the storyboard itself frames 60% of shots tight, and the images being judged predated the previous sprint's run entirely. 999 tests pass. Live: close 3.3%, wide/full body 56.7%, 19 of 30 shots full body.
- Handed off to: generating images from the new prompts and actually looking at them; and deciding which command owns `shot_image_prompts.json`.

### 2026-07-20 — Sprint 026 (first spec) Cinematic Director delivered
- Shots are now directed rather than described (ADR-039). New `cinema` CLI writes `cinematic_direction.json` and recomposes `shot_image_prompts.json`. `SceneDirector` sets each scene's purpose/emotion/conflict/beat; `ShotDirector` sets each shot's type/angle/lens/composition/blocking/lighting/action/motion. 85mm is structurally prevented from becoming the default; static actions are replaced with active ones; a conflict nobody wrote stays empty. Deterministic and offline; `PromptComposer` rewritten with `direction` optional so 025B/C callers are unaffected. 935 tests pass.
- Handed off to: re-running `character memory` after `cinema` (shared prompt file), and generating images to judge whether the coverage actually reads as a film.

### 2026-07-20 — Sprint 025C Character Memory Engine delivered
- Each character's look is frozen in `character_memory.json` (canonical face/hair/body/clothes/weapon/expression/palette + reference image + appearance hash) and every prompt restates it (ADR-038). The canon is reloaded and never overwritten; the first image that exists becomes the reference and is never re-pointed. `AppearanceValidator` scores 8 attributes and rebuilds sub-threshold prompts; `appearance_scores.json` records the result. Reference described in words because no shipped image driver accepts one. New `character memory` CLI. 899 tests pass; average appearance score 97 on the real film.
- Handed off to: generating images from the enriched prompts so the remaining characters adopt references, and wiring the image stage to `shot_image_prompts.json`.

### 2026-07-20 — Sprint 025B Visual Continuity Engine delivered
- Image prompts are now composed from the character bible, world bible, visual context and the shots either side of each one (ADR-037). New `continuity` CLI writes the two bibles, `visual_context.json`, `shot_image_prompts.json` and `prompt_scores.json`. Bibles are derived then hand-editable; continuity is asserted only within a scene; sub-threshold prompts are recomposed at escalating explicitness. Deterministic and offline - `image_prompts.json`, providers, video and compose all untouched. 852 tests pass; average score 93 on the real 30-shot storyboard.
- Handed off to: enriching `world_bible.json` by hand (weather/era/motifs), and wiring the image stage to the new prompts.

### 2026-07-20 — Sprint 025 AI Video Generation delivered
- `storyboard.json` -> `output/video_clips/shot_NNN.mp4` + manifest (ADR-036). Shots merged into 4-8s clips within scene boundaries, timeline preserved exactly (30 -> 20 clips, 90.0s). Provider contract now `generate(request, references)` with character / scene / previous-clip stills; mock and Kling updated. Portrait 1080x1920 from VideoSettings, so compose is unaffected. `--resume` reuses rendered clips. 805 tests pass. Two gaps reported: 10 clips fall under 4s (upstream shot lengths), and character reference images are never populated (`reference_image` unset since Sprint 019).
- Handed off to: longer shots from `director`, populating character stills, and a live render.

### 2026-07-20 — Sprint 024 (two specs) delivered
- **OpenRouter** (ADR-034): the director runs on `deepseek/deepseek-chat-v3` through a new provider satisfying the existing `LLMProvider` protocol; `AIVF_DIRECTOR_PROVIDER` selects it independently of the story pipeline. No business logic changed. Live API unverified (no credentials).
- **Storyboard** (ADR-035): `movie_directed.json` -> `storyboard.json`; every shot flattened onto a timeline with absolute speech windows, overlap-mapped subtitles, clipped audio slices and a still-frame image prompt. Offline and deterministic. Live: 30 shots / 10 scenes / 90.0s. Surfaced that `narration.srt` (109.5s) is mistimed against `narration.mp3` (66.7s); the CLI now warns.
- 770 tests pass. Handed off to: retiming the subtitles, and a live OpenRouter run.

### 2026-07-20 — Sprint 023 Batch Director + Shot Planner delivered
- Scenes are now broken into **shots** (13 fields each, 3-8 per scene, 2-5s) by a single LLM request (ADR-033; ADR-032's one-call rule retained). `DirectorNotes`/`director_prompt` replaced by `DirectedScene.shots`. Parser renumbers ids, clamps durations, trims overflow; each shot's prompt is composed from the character library. Fixed an appearance leak via the injected scene prompts. 667 tests pass; stub-verified on the real 10-scene movie (1 request, 30 shots). **Live API blocked by quota.**
- Handed off to: re-running `director` when quota resets; wiring the video stage to per-shot prompts when specified.

### 2026-07-20 — Sprint 022B Director Single-Request Refactor delivered
- Reverted 022A's per-scene planning: the director now plans the whole movie in **one** Gemini request (all scenes + character library + locations → one `{"scenes":[...]}` answer, mapped back by `scene_id`). Retries re-ask that request; invalid JSON re-asks up to 3×. Partial/`--resume`/report retained. ADR-032 supersedes ADR-031 §1–2. 659 tests pass. **No successful live run — the key is quota-exhausted.** Two open findings: the google-genai SDK retries internally (~4× amplification) and `RetryPolicy` caps the server's `retry_after` hint below what it asks for.
- Handed off to: re-running the director once quota resets; Lead decision on the two retry findings.

### 2026-07-20 — Sprint 022A Director Provider Resilience delivered
- Fixed the real defect: the Gemini client caught only `APIError`, so connection/read timeouts escaped untranslated and unretried (502/503/504 were already fine). Director now plans **one scene per request** with 5 retries (1s/2s/4s/8s/16s ±20% jitter); a failed scene is isolated and the run continues. Partial output → `movie_directed.partial.json`; `--resume` re-plans only failures; report shows directed/failed/retries. ADR-031. 654 tests pass. **No successful live run** — `DIRECTOR_MODEL=gemini-2.5-flash` 404s on this key and the key then hit its quota.
- Handed off to: re-running the director once the model/quota issues are resolved.

### 2026-07-20 — Sprint 022 AI Director delivered
- New stage Movie → **Director** → Directed Movie (ADR-030): `DirectorService` plans 16 shot fields per scene via the LLM (retry once) and composes a pure, deterministic `director_prompt` aimed at AI **video** models — library identity, shot, camera motion, subject/hand/pose/expression motion, hair/cloth/environment motion, lighting, mood, setting, transitions, temporal-coherence directive. `DirectedScene`/`DirectedMovie` subclass the Movie Builder's models, so `movie.py` is untouched and the output still reads as a `Movie`. New `director` CLI → `output/movie_directed.json`. 615 tests pass; verified live (10 scenes, all 16 fields, 5 distinct shot types).
- Handed off to: wiring the video stage to `director_prompt` when specified, then the next Sprint spec.

### 2026-07-20 — Sprint 021A Cost Guard delivered
- `video generate` gains `--dry-run` (preview provider/model/scenes/jobs/duration/cost, submits nothing, needs no credentials), `--limit N`, and a confirmation prompt for any provider but `mock` unless `--yes` (defaults to No; non-interactive declines; declining exits 0). New `cost.py` `GenerationPlan` backs both the preview and the manifest. Manifest `cost` → `estimated_cost` + `actual_cost` (breaking). ADR-029. 560 tests pass; verified live on the real `movie_consistent.json`.
- Handed off to: cheap live Kling validation (`--dry-run`, then `--limit 1`), then the next Sprint spec.

### 2026-07-20 — Sprint 021 Kling Video Provider delivered
- New `infrastructure/video/providers/kling/` (ADR-028): `RealKlingClient` behind a seam + `KlingVideoProvider` (image-to-video; `submit_job`/`poll_job`/`download_result`/`cancel_job`), exponential-backoff retry, poll timeout + cancel-on-overrun, clean error translation. `video generate --movie` → `scene_NNN.mp4` + `manifest.json` with a phase progress bar. `mock` remains the default driver; `video doctor` now judges only the configured provider. compose/TTS/image untouched. 533 tests pass (no network); end-to-end verified against a local stub HTTP server. **Live Kling API unverified — no credentials.**
- Handed off to: operator validation against the live Kling API, then the next Sprint spec.

### 2026-07-20 — Sprint 020 Video Provider Layer delivered
- New `infrastructure/video/providers/` (ADR-027): `VideoProvider` protocol, vendor-neutral request/result models + `VideoJobStatus`, `VideoProviderRegistry` (config-driven, no global state), `VIDEO_PROVIDER` settings section, and a development `MockVideoProvider` rendering `output/video_clips/scene_NNN.mp4` with the existing local ffmpeg pipeline. New `video providers` / `video doctor` / `video generate` CLI. **Abstraction only — no commercial provider integrated**; the slideshow compose pipeline is untouched and backward compatible. 463 tests pass; request/argv flow verified against the real `movie_consistent.json` (a real render still awaits an ffmpeg install).
- Handed off to: next Sprint spec (a real video provider only once the Lead approves one).

### 2026-07-20 — Sprint 019 Character Consistency Engine delivered
- New `character build` / `character inject` CLI + `infrastructure/character/` (ADR-026): deterministic, offline `CharacterConsistencyService` (one master prompt, normalized appearance/outfit, merged negative prompt, SHA-256 seed, duplicate merge) → `output/character_library.json`; `CharacterPromptInjector` (prepend master / append negative / preserve original, idempotent) → `output/movie_consistent.json`. Additive — Movie Builder and image provider untouched. 411 tests pass; verified live (4 profiles, 10/10 scenes injected).
- Handed off to: next Sprint spec (wiring `movie_consistent.json` into image generation when specified).

### 2026-07-20 — Sprint 018 Character & Scene Bible (Movie Builder) delivered
- New `movie` CLI + domain models (`Movie/Character/Appearance/Location/Camera/Scene`) + `MovieBuilder` (ADR-025): Chapter → `output/movie.json` with deduped characters (fixed appearance) and cinematic scenes (camera/action/emotion/image_prompt/video_prompt). Additive — no existing stage modified. 374 tests pass; verified live (schema-valid movie.json, 4 chars / 5 locations / 8 scenes).
- Handed off to: next Sprint spec (pipeline wiring / further stages when specified).

### 2026-07-20 — Sprint 017 Video Composer delivered
- New `infrastructure/video/` (ffmpeg-only, ADR-024): pure `build_ffmpeg_command`, `parse_srt_cues`, `FfmpegVideoComposer` (implements the existing `VideoComposer` protocol), `compose` CLI → `output/video/final.mp4` + `metadata.json`. 1080x1920/H.264/AAC, Ken Burns + crossfades + burned subtitles, reuse-last-image, retry-once, ffmpeg verified via `check_ffmpeg()`. 353 tests pass (ffmpeg mocked); live render pending an ffmpeg install.
- Handed off to: next Sprint spec (upload/pipeline wiring when specified).

### 2026-07-20 — Sprint 016 Subtitle Generation delivered
- New transcription provider layer (port + Gemini driver + factory + settings, ADR-023) + `subtitle` CLI → UTF-8 Vietnamese `output/subtitles/narration.srt`, timed to the narration; retry ×3, skip-unless-`--force`. `to_srt` formatter + `SubtitleStorage`. 325 tests pass; verified live (21-cue SubRip).
- Handed off to: next Sprint spec (video composition / ffmpeg when specified).

### 2026-07-20 — Sprint 015 Voice Generation delivered
- `tts` primary flag → `--input` (`--chapter` alias); reuses `SpeechProvider`, Vietnamese default, retry ×3, skip-unless-`--force`. Fixed a legacy-Windows cp1252 crash (Braille spinner) that was dropping `metadata.json` after saving `narration.mp3` — stdout now switched to UTF-8. 295 tests pass; verified live (66.7s narration, both files written).
- Handed off to: next Sprint spec (subtitle/video stages when specified).

### 2026-07-20 — Sprint 014 Generate Real Images delivered
- `image` command: per-file skip, continue-on-failure, generated/skipped/failed summary, richer manifest (`filename/prompt/width/height/created_at`) with dimensions parsed from image bytes. Provider/storage untouched (work-dir + atomic rename). 294 tests pass; verified live (6 skipped, real dims).
- Handed off to: next Sprint spec (subtitle/video stages when specified).

### 2026-07-20 — Sprint 013 Pollinations Image Provider delivered
- New free, key-less `PollinationsImageProvider` behind the existing `ImageProvider` port (httpx client seam); registered as the `pollinations` driver and made the **default** (model `flux`). Gemini Imagen unchanged/selectable. ADR-022. 287 tests pass; 6 images generated live for free.
- Handed off to: next Sprint spec (subtitle/video stages when specified).

### 2026-07-19 — Sprint 012 Implement Image Generation (image hardening) delivered
- Enhanced the existing `image`: `001.png` naming (empty-prefix `ImageStorage`), `manifest.json`, image retry default 1→3, and `--force`/skip-if-`001.png`-exists. Reused `ImageProvider`, no refactor. 241 tests green; no new ADR.
- Handed off to: next Sprint spec (subtitle/video stages when specified).

### 2026-07-19 — Sprint 013 Voice Generation (tts hardening) delivered
- Enhanced the existing `tts`: speech retry default 1→3, and `--force`/skip-if-`narration.mp3`-exists. Reused `SpeechProvider`, no refactor. 237 tests green; no new ADR.
- Handed off to: next Sprint spec (subtitle/video stages when specified).

### 2026-07-19 — Sprint 011 Asset Pipeline Foundation delivered
- Built `asset_pipeline` (`AssetResult`, generator Protocols, `AssetPipelineRunner`) wrapping the existing image/speech providers; subtitle/video as contracts (raise until wired); `assets` status CLI. 233 tests green; ADR-021 recorded (renumbered from the Lead's "010").
- Handed off to: next Sprint spec (subtitle/video stages when specified).

### 2026-07-19 — Sprint 010 Voice Generator delivered
- Built `SpeechProvider` Protocol + `GeminiSpeechProvider` (Gemini TTS) + `SpeechProviderFactory` + `AudioStorage` + `tts` CLI (Rich spinner). Reused shared errors/retry/health. PCM→WAV under `output/audio/narration.mp3` + `metadata.json`. 225 tests green; ADR-020 recorded.
- Handed off to: next Sprint spec (no future stages implemented).

### 2026-07-19 — Sprint 009 Pipeline Orchestrator (Phase 1) delivered
- Built `PipelineRunner` composing the four existing generators + `generate` CLI (Rich progress); sequential, persist-after-each, stop-on-failure. 198 tests green (incl. integration); live end-to-end verified; ADR-019 recorded.
- Handed off to: next Sprint spec (no future stages implemented).

### 2026-07-19 — Sprint 008 Image Provider Layer delivered
- Built `ImageProvider` Protocol + `GeminiImagenProvider` (Imagen) + `ImageProviderFactory` + `ImageStorage` + `image` CLI (Rich progress bar). Reused shared errors/retry/health. Saves PNGs to `output/images/`. 189 tests green; ADR-018 recorded.
- Handed off to: next Sprint spec (no future stages implemented).

### 2026-07-19 — Sprint 007 Image Prompt Generator delivered
- Built `ImagePromptGenerator` (infra) + `ImagePrompt` (domain) + `image-prompt` CLI; JSON mode, retry-once, injected style/aspect, `output/image_prompts.json`; `read_chapter` loader. Text only, no images. 169 tests green; ADR-017 recorded.
- Handed off to: next Sprint spec (no future stages implemented).

### 2026-07-19 — Sprint 006 Chapter Generator delivered
- Built `ChapterGenerator` (infra) + `StoryChapter` (domain) + `chapter` CLI; JSON mode, retry-once, computed duration, `output/chapter.json`; `read_outline` loader. 150 tests green; ADR-016 recorded.
- Handed off to: next Sprint spec (no future stages implemented).

### 2026-07-19 — Sprint 005 Story Outline Generator delivered
- Built `OutlineGenerator` (infra) + `StoryOutline`/`ChapterOutline` (domain) + `outline` CLI; JSON mode, chapter-count validation, retry-once, `output/story_outline.json`; `read_idea` selector. 130 tests green; ADR-015 recorded.
- Handed off to: next Sprint spec (no future stages implemented).

### 2026-07-19 — Sprint 004 Story Idea Generator delivered
- Built `IdeaGenerator` (infra) + `StoryIdea`/`IdeaBrief` (domain) + `idea` CLI; JSON mode, retry-once, `output/ideas.json`. Evolved `story/idea.md`. 108 tests green; ADR-014 recorded.
- Handed off to: next Sprint spec (no future stages implemented).

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
