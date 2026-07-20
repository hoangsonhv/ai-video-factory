# CHANGELOG

**Purpose:** The human-readable, chronological record of notable changes to AI Video Factory across releases. It tells users and contributors what changed, when, and why — distinct from git history (mechanical) and `03_ROADMAP.md` (forward-looking intent).

**Owner:** Technical Lead.

**When to update:** On every release/version bump, and by accumulating entries under `[Unreleased]` as meaningful changes land (new stage, new provider, behavior change, breaking change). At release time, `[Unreleased]` is renamed to the version with a date.

**Format:** Based on [Keep a Changelog](https://keepachangelog.com/); versions follow [Semantic Versioning](https://semver.org/). Change groups: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

---

## [Unreleased]

### Added
- **Sprint 026 (second spec) - Cinematic Shot Planner (ADR-040).** The images were coming back as near-identical portraits; this plans every frame so they cannot.
  - New CLI `ai-video-factory shot-plan --storyboard output/storyboard.json`, writing **`output/shot_plan.json`** and **`output/shot_statistics.json`**, and rebuilding `shot_image_prompts.json`.
  - **Coverage follows content.** Each scene is classified from its own words (opening, conversation, action, combat, emotion, landscape) and the rule for that kind sets the size the scene opens on and dominates it with.
  - **The film is validated as a distribution**, not shot by shot - close <=20%, medium 20-35%, wide/full body >=40%, establishing >=5% - and **re-planned automatically** until it balances. Rebalancing demotes the least-justified shot first and never trades away a size a scene's kind mandates.
  - **Every frame must state a foreground, midground or background**, derived from the shot, the scene's location and the world bible. A frame that states nothing anywhere is **rejected** - that is exactly the shot that returns as a face on a blank backdrop.
  - **`PromptComposer` rewritten** to the specified order: Character, Environment, Action, Shot Type, Camera Distance, Camera Angle, Lens, Composition, Lighting, Motion Hint, Negative Prompt.
  - **Portrait prevention both ways**: close/portrait/headshot/face-focus language is stripped from the source text unless the plan approved a close size (and raises if any survives), and a non-close shot refuses portrait framing in its own negative prompt.
  - **85mm can never be a default** - lenses come from a table keyed by shot size, reachable at 85mm only on the closest sizes and alternating with 135mm there.
  - On the real 30-shot film: close **3.3%**, medium 33.3%, wide/full body **56.7%**, establishing 6.7% (valid after 3 automatic re-plans); body visibility **19 full body, 10 waist up, 1 head-and-shoulders**. Deterministic and offline; no provider, video or compose change; `image_prompts.json` untouched. 64 new tests (999 total).
  - **Supersedes the Cinematic Director** (ADR-039) as the producer of `shot_image_prompts.json`. The `cinema` command still works and is still tested - nothing was removed - but `shot-plan` is the path to use; running both is not meaningful, as the last one wins the prompts file.

### Added
- **Sprint 026 (first spec) - Cinematic Director (ADR-039).** Shots are now *directed* rather than described: every one carries a purpose, camera, composition, action, lighting and emotion.
  - New CLI `ai-video-factory cinema --storyboard output/storyboard.json`, writing **`output/cinematic_direction.json`** and rewriting `shot_image_prompts.json`.
  - **`SceneDirector`** gives each scene a purpose, emotion, conflict and story beat, placed by where the scene falls in the film. A conflict nobody wrote is **left empty** rather than invented.
  - **`ShotDirector`** picks the shot type, camera angle, lens, composition, blocking, lighting, action and motion hint per shot. The coverage cycle is **offset per scene**, so consecutive scenes are not filmed shot-for-shot identically.
  - **85mm is no longer the house default.** A lens is chosen from a table keyed by shot size; 85mm is reachable only on a close up or extreme close up and alternates with 135mm there. On the real film: 24mm x12, 35mm x7, 50mm x5, 85mm x3, 135mm x3, across six shot types.
  - **"Standing" is replaced, not decorated** - a static description becomes walking, running, drawing a sword, casting a spell and so on; a description that already carries a verb is kept.
  - **`PromptComposer` rewritten** to the director's order (Character, Environment, Action, Camera, Composition, Lighting, Lens, Motion Hint, Negative) with the continuity sections folded in. `direction` is optional, so every existing caller composes exactly as before.
  - Deterministic and offline - no LLM call, no cost, same input always yields the same shot list. No provider, video or compose change; `image_prompts.json` untouched. 36 new tests (935 total).
  - **Note:** `cinema` rewrites `shot_image_prompts.json`, which it shares with Sprints 025B/C - re-run `character memory` afterwards to restore the frozen-identity block. The CLI says so.

### Added
- **Sprint 025C - Character Memory Engine (ADR-038).** Every image of a character now restates the same frozen identity, so the tenth looks like the first.
  - New **`output/character_memory.json`** holds each character's canonical face, hair, body, clothes, weapon, expression and palette, plus its reference image and an `appearance_hash`.
  - **The canon is frozen after the first run** - reloaded, never overwritten, so hand edits and remembered values both survive. The **first image that exists** for a character becomes its reference and is never re-pointed.
  - **`AppearanceValidator`** scores eight attributes (hair, face, clothes, weapon, colours, gender, age, style); below the threshold the prompt is rebuilt with the appearance stated more insistently. An attribute the memory never captured scores 0 and is marked `(not remembered)`, rather than being excused.
  - New **`output/appearance_scores.json`** reports every prompt's score and what it failed to pin. A changed appearance whose hash no longer matches is flagged as drift.
  - **Reference handling is provider-aware**: a driver that accepts an image reference gets the path attached; the ones shipped today do not, so the reference is described in the prompt instead. No provider was changed.
  - New CLI `ai-video-factory character memory --storyboard output/storyboard.json`. Deterministic and offline; `image_prompts.json`, the providers, the video stage and compose are untouched. 47 new tests; average appearance score 97 on the real film.

### Added
- **Sprint 025B - Visual Continuity Engine (ADR-037).** Image prompts are now built from the whole film, not from one shot, so consecutive stills read as frames of the same movie.
  - New `ai-video-factory continuity --storyboard output/storyboard.json` writing **`character_bible.json`**, **`world_bible.json`**, **`visual_context.json`**, **`shot_image_prompts.json`** and **`prompt_scores.json`**.
  - **The bibles are derived** from the character library and the movie, then written out - and a later run **keeps any hand edits**, which is the intended way to enrich art direction.
  - **Every prompt carries** the character bible, world bible, visual context, previous / current / next shot, camera, lens, lighting, art direction, cinematic style and negatives. Continuity is asserted only *within* a scene, never across a cut.
  - **`PromptScorer`** scores character, environment, style, story and camera continuity. Below the threshold (default 90) the prompt is **recomposed at a higher level of explicitness** - a real rewrite, not a reroll. A shortfall caused by missing upstream data is reported rather than looped over.
  - Deterministic and offline: no provider call, no video change, and **`image_prompts.json` is left untouched** - the new prompts go to their own file, schema-compatible so the image stage can be pointed at them later. 47 new tests; average score 93 on the real 30-shot storyboard.

### Added
- **Sprint 025 - AI video generation from the storyboard (ADR-036).** `output/storyboard.json` -> `output/video_clips/shot_NNN.mp4` + `manifest.json`.
  - **Shots are merged into 4-8 second clips** within scene boundaries, preserving the timeline exactly (30 shots -> 20 clips, 90.0s unchanged on the real storyboard). Durations are never stretched; a scene that cannot split evenly yields a short clip, **and the CLI says so**.
  - **The provider contract is now `generate(request, references)`.** `ClipReferences` offers the character stills, the scene still and the **previous clip**, so a provider that supports continuation can hold character, costume and environment consistency across clips. Mock and Kling both updated; a provider that supports none of them ignores it.
  - Clips are rendered at the configured frame (portrait 1080x1920, 9:16) so they still match compose, which is untouched. Landscape is an env change, not a code change.
  - CLI `ai-video-factory video generate --storyboard output/storyboard.json`, plus **`--resume`** (reuse clips already on disk without re-spending). `--movie` keeps Sprint 021's scene-per-clip route working.
  - The manifest now records `clip_id` and the `shot_ids` each clip covers, so the merge is auditable. 48 new tests.

### Changed
- **Clip files are named `shot_NNN.mp4`** (previously `scene_NNN.mp4`), numbered by clip rather than by scene, per the Sprint 025 spec. Existing `scene_*.mp4` files from earlier runs are left untouched and will not be overwritten.

### Added
- **Sprint 024 - Storyboard Builder (ADR-035).** A new deterministic stage that flattens the directed movie onto a timeline: `output/movie_directed.json` -> `output/storyboard.json`.
  - Every shot of every scene becomes one addressable `StoryboardShot` with the 20 specified fields, including an absolute `speech_start`/`speech_end`, the `subtitle` spoken over it, and the `audio_segment` slice of the narration track.
  - **Narration is mapped by overlap onto the shots**; shot durations are never rewritten to chase it, so the director's 2-5s rule holds. Where the two lengths disagree the storyboard reports the drift.
  - `image_prompt` is composed as a **still** (identity + framing + lighting, no motion); `video_prompt` is carried through from the director.
  - CLI `ai-video-factory storyboard --movie output/movie_directed.json` (`--subtitles`, `--library` to override). Offline - no provider call, no compose change. 50 new tests.
  - **Warns when the subtitles are mistimed** (`.srt` span vs the real audio length differing by >10%) rather than emitting a silently misaligned storyboard.

### Changed
- **Sprint 024 - OpenRouter as the director's provider (ADR-034).** The director now runs on OpenRouter instead of Gemini, whose quota had been blocking live runs.
  - New `OpenRouterProvider` satisfying the **existing** `LLMProvider` protocol, plus `RealOpenRouterClient` behind a seam. No business logic changed - only which provider the director is handed.
  - `AIVF_DIRECTOR_PROVIDER` selects the director's provider independently of the story pipeline; `AIVF_OPENROUTER_API_KEY` / `AIVF_OPENROUTER_MODEL` configure it, defaulting to **`deepseek/deepseek-chat-v3`**.
  - `count_tokens()` estimates (~4 chars/token) - OpenRouter exposes no counting endpoint. 53 new tests, all HTTP mocked.

### Changed
- **Sprint 023 — Batch Director + Shot Planner (ADR-033).** The director now breaks each scene into **shots** — the unit an AI video model actually renders — instead of describing a whole scene with one block of adjectives. Still **exactly one LLM request per movie** (ADR-032 stands).
  - **New schema (breaking):** `DirectedScene.director` + `director_prompt` are replaced by `shots: [Shot, ...]`. Each shot carries `id`, `duration`, `camera`, `camera_motion`, `lens`, `framing`, `subject`, `action`, `expression`, `environment_motion`, `lighting`, `transition` and `video_prompt`.
  - **3-8 shots per scene, 2-5 seconds each** — with the conflict resolved honestly: three 2s shots need a 6s scene, so a 5s scene gets 2 shots rather than an impossible 3. The prompt states a per-scene target computed from its length.
  - **Deterministic repair:** shot ids are renumbered 1..N per scene, durations are clamped into range (a missing one falls back to an even split of the scene), and more than eight shots are trimmed. Structural failures are reported, never guessed at.
  - **Each shot's `video_prompt` is composed** from the character library's master prompt plus the shot's own camera/motion/setting fields, with the model's one-line description folded in — so identity comes from the library, never the model.
  - **Fixed a leak found in verification:** `movie_consistent.json` prepends each master prompt to every scene prompt, so the appearance the director is told not to describe was reaching it anyway. It is now stripped before the request is built.
  - Partial output, `--resume` (now keyed on "scene has shots") and the direction report are unchanged. Tests rewritten for shots; 667 pass.

### Changed
- **Sprint 022B — the director plans the whole movie in one request (ADR-032, supersedes ADR-031 §1–2).** Sprint 022A's per-scene planning made one Gemini call per scene, which exhausted a rate-limited key ~10× faster and multiplied token cost. Reverted to a **single** request.
  - The prompt now carries every scene, the **character library** (ids and voice notes only — never appearance, which would break consistency) and the **locations**; the model answers with one `{"scenes": [...]}` block, mapped back onto the movie by `scene_id`.
  - **Retries re-ask that one request, never per scene**: transient failures (429/5xx, connection and read timeouts) back off with jitter, and an unparseable answer re-asks the whole question up to three times.
  - A scene the answer omits is still left unplanned and saved to the partial file; `--resume` re-asks only those scenes — again in a single request.
  - Kept from 022A: the Gemini transport-error fix, opt-in `RetryPolicy` jitter, partial output, `--resume`, and the direction report.

### Fixed
- **Sprint 022A — Director provider resilience (ADR-031):** the `director` command no longer dies on a transient Gemini failure.
  - **Root cause fixed:** the Gemini client caught only the SDK's `APIError`, which exists only once an HTTP response arrives. Connection timeouts, read timeouts and dropped sockets escaped as raw `httpx` exceptions — untranslated and unretried. They are now mapped to retryable provider errors at every SDK call site. (502/503/504 were already mapped and retried correctly.)
  - **Per-scene planning**: the director now issues one request per scene instead of one for the whole movie, so a failure costs one scene rather than the entire run. Each request carries the previous scene's shot plan, preserving cross-scene rhythm.
  - **Retry**: five retries per scene with exponential backoff (1s, 2s, 4s, 8s, 16s) and **±20% jitter**, on 429/500/502/503/504 and connection/read timeouts; terminal errors are not retried. Jitter and a retry hook were added to the shared `RetryPolicy` as opt-in parameters, leaving every other provider's timing unchanged.
  - **Failure isolation**: a scene that exhausts its retries is left unplanned and the run continues to the next scene.
  - **Partial output**: a run with some successes writes `output/movie_directed.partial.json` and exits non-zero; a complete run writes `movie_directed.json` and removes the stale partial.
  - **`--resume`** reuses every already-directed scene and re-plans only the failures.
  - **Final report**: directed / failed / retry count / skipped, plus the failed scene ids.
  - 39 new tests (503, 502, 504, connection and read timeouts, retry ceiling, backoff-with-jitter, isolation, partial save, resume). **Note:** per-scene planning makes ~10× as many requests for a ten-scene movie.

### Added
- **Sprint 022 — AI Director (ADR-030):** a new stage that replaces generic video prompts with cinematic shot planning. Movie → **Director** → Directed Movie. Providers, image generation and compose are untouched.
  - New domain models (`domain/value_objects/director.py`): `DirectorNotes` (shot_type, camera_angle, camera_motion, lens, framing, subject_motion, facial_expression, hand_action, body_pose, hair_motion, cloth_motion, environment_motion, lighting, mood, transition_in, transition_out), plus `DirectedScene`/`DirectedMovie` which **subclass** the Movie Builder's models — `movie.py` is untouched and `movie_directed.json` still validates as a plain `Movie`.
  - New `infrastructure/director/`: `DirectorService` (renders `prompts/director/shot_plan.md`, LLM in JSON mode, retry once), a **pure** `build_director_prompt()`, and an honest fallback that fills omitted fields from the scene's own camera/action/emotion — never with invented filler.
  - **`director_prompt` targets AI video models, not image models**: identity from the character library first (so Sprint 019's consistency holds — the template forbids re-describing characters), then shot and camera motion, a motion breakdown (subject/hands/pose/expression), secondary motion a still prompt never carries (hair/clothing/environment), lighting, mood, setting, duration, transitions, and a temporal-coherence directive.
  - CLI `ai-video-factory director --movie output/movie_consistent.json [--library …]` → `output/movie_directed.json`. Every original scene field, including `video_prompt`, is preserved verbatim — the director adds, never rewrites. 60 new tests; verified live on the real 10-scene movie.

### Added
- **Sprint 021A — Cost Guard (ADR-029):** `video generate` can no longer spend money by accident.
  - **`--dry-run`** prints the plan — provider, model, scene count, estimated jobs, estimated duration, estimated cost — and submits nothing. It needs no credentials, so the preview never fails for want of a key.
  - **`--limit N`** submits only the first N scenes; the plan shows the run as limited so a capped run is never mistaken for a full one.
  - **Interactive confirmation** for any provider but `mock` unless `--yes` is passed. The prompt defaults to **No**, and a non-interactive stream (CI, piped input) declines rather than spending unattended. Declining exits 0 — it is a choice, not a failure.

### Changed
- **`manifest.json` cost fields (breaking):** the ambiguous `cost` is replaced by **`estimated_cost`** (projected before the run) and **`actual_cost`** (what the finished job worked out to; `0.0` for a failed scene), with `total_estimated_cost` / `total_actual_cost` replacing `total_cost`. Both are `0.0` when no `cost_per_second` rate is configured — meaning *unknown*, not *free*. The manifest is a regenerated artifact, so no migration is provided.

### Added
- **Sprint 021 — Kling AI Video Provider (ADR-028):** the first real AI video driver, behind the Sprint 020 contract. The compose, TTS and image stages are untouched.
  - New `infrastructure/video/providers/kling/`: `RealKlingClient` (the only module doing HTTP, behind a `KlingClient` seam), `KlingJob` + vendor status mapping, and `KlingVideoProvider` implementing `VideoProvider`.
  - **Image-to-video**: each scene's generated image + its `video_prompt` → one clip. The async lifecycle is exposed as `submit_job()`, `poll_job()`, `download_result()` and `cancel_job()`, composed by `generate()`.
  - **Resilience**: exponential-backoff retry on 429/503/timeout (terminal errors are not retried), a per-request timeout plus a separate `poll_timeout` for the whole remote render, and **cancellation of a job that overruns** so nothing is left running and billing. Every failure is translated into `VideoProviderError` — a provider outage produces a clean per-scene failure, never a crash.
  - Configuration reuses the `VIDEO_PROVIDER` section: `AIVF_VIDEO_PROVIDER__API_KEY` (`KLING_API_KEY`), `__BASE_URL` (`KLING_BASE_URL`), `__MODEL` (`KLING_MODEL`), plus `__POLL_INTERVAL`, `__POLL_TIMEOUT` and `__COST_PER_SECOND`. **`mock` remains the default driver** so the CLI still works without a paid key.
  - CLI `ai-video-factory video generate --movie output/movie_consistent.json` (`--scene` kept as an alias, `--images` to override the image directory): submits, polls, downloads and saves `output/video_clips/scene_001.mp4`, … with a phase progress bar (submitting → waiting → downloading → completed), then writes `output/video_clips/manifest.json` (scene_id, provider, model, status, duration, cost, remote_job_id, filename + total_cost).
  - 70 new tests — HTTP mocked end to end (httpx `MockTransport`), covering payload/response parsing, retry and backoff, the poll-timeout-and-cancel path, download, manifest and CLI. No network in the test suite.

### Changed
- **`video doctor` fails only on the *configured* provider.** With more than one driver registered, an unconfigured alternative (Kling with no API key while `mock` is selected) is now reported for information instead of failing the command.

### Added
- **Sprint 020 — AI Video Provider Layer (ADR-027):** the **abstraction only** for AI video generation — **no commercial provider (Veo, Kling, Runway, Hailuo, …) is integrated**, and the existing slideshow compose pipeline is untouched and fully backward compatible.
  - New `infrastructure/video/providers/` subpackage (kept under the existing `infrastructure/video/`): a vendor-neutral `VideoProvider` protocol (`generate`, `supported_models`, `health_check`), the `VideoGenerationRequest` / `VideoGenerationResult` models, and a `VideoJobStatus` enum (`queued`, `running`, `completed`, `failed`).
  - `VideoProviderRegistry` maps a config driver string to a provider — register / list / create / create-default / concurrent health-check. Constructed rather than module-global, so there is no global mutable state.
  - New `VIDEO_PROVIDER` configuration section (`AIVF_VIDEO_PROVIDER__PROVIDER` / `__MODEL` / `__TIMEOUT` / `__RETRY_COUNT`), separate from the ffmpeg composition settings (`AIVF_VIDEO__*`), which are unchanged.
  - `MockVideoProvider` (**development only**): renders one clip per scene locally with the existing ffmpeg pipeline → `output/video_clips/scene_001.mp4`, `scene_002.mp4`, … using a reference image when available and a colour card otherwise. Honours the configured timeout and retry count; reuses the composer's injectable runner seam so tests never invoke ffmpeg.
  - CLI `ai-video-factory video providers`, `video doctor`, and `video generate --scene output/movie_consistent.json` (per-scene status table, continues past a failed scene, non-zero exit if any failed). 52 new tests. No existing generator/image/TTS/compose code changed.

### Added
- **Sprint 019 — Character Consistency Engine (ADR-026):** a new `character` command group that guarantees every scene renders a character the same way — **additive; the Movie Builder and the image provider are untouched**.
  - New domain models (`domain/value_objects/character_library.py`): `CharacterLibrary`, `CharacterProfile`, `NormalizedAppearance`, `NormalizedOutfit` (frozen, matching the `character_library.json` schema).
  - New `infrastructure/character/`: `CharacterConsistencyService` distils the movie's cast into **one master prompt per character**, normalizes appearance/outfit, generates a merged negative prompt, derives a **deterministic seed** (SHA-256 of the character id) and **merges duplicate character records**. Fully offline — no AI provider, no network, byte-identical output on every run.
  - `CharacterPromptInjector` rewrites each scene's `image_prompt` / `video_prompt` as `<master prompts> | <original prompt> | negative: <terms>` — the master prompt is prepended, the negative prompt appended, and the scene's own direction preserved verbatim. Injection is idempotent; a scene referencing an unknown character id fails loudly.
  - CLI `ai-video-factory character build --input output/movie.json` → `output/character_library.json`, and `ai-video-factory character inject --movie output/movie.json` → `output/movie_consistent.json` (`--library` overrides the library path). 37 new tests (models incl. JSON-schema validation, normalization, seed generation, prompt generation, duplicate merge, injection, CLI). No existing generator/image/TTS/compose code changed.

### Added
- **Sprint 018 — Character & Scene Bible / Movie Builder (ADR-025):** a new `movie` command that builds a structured movie bible from a chapter — **additive; the existing pipeline is untouched**.
  - New domain models (`domain/value_objects/movie.py`): `Movie`, `Character`, `Appearance`, `Location`, `Camera`, `Scene` (frozen, matching the `movie.json` schema).
  - New `MovieBuilder` (`story/movie_builder.py`) + parser/writer + `prompts/story/movie.md`: extracts every character and **deduplicates** them with a **fixed appearance** (id-based, first wins), and generates per-scene camera language, action, emotion, image_prompt, and video_prompt via the configured LLM (JSON mode, retry-once).
  - CLI `ai-video-factory movie --input output/chapter.json` → `output/movie.json`. Pipeline: Topic → Idea → Outline → Chapter → **Movie Builder**. 21 new tests (models, parser incl. JSON-schema validation, builder, CLI). No existing generator/image/TTS/compose code changed.

### Added
- **Sprint 017 — Video Composer (ADR-024):** a new `compose` command that renders the final portrait MP4 from existing assets using ffmpeg only.
  - New `infrastructure/video/`: a pure, unit-testable `build_ffmpeg_command()` (argv generator), `parse_srt_cues()` timing reader, `FfmpegVideoComposer` (satisfies the existing `VideoComposer` protocol — no new port, no factory), and a video-metadata writer.
  - Composition: 1080x1920, 30 fps, H.264/AAC; one image per subtitle cue (reusing the last image when images < cues); per-image Ken Burns slow zoom; smooth crossfades; burned-in subtitles; narration audio (`-shortest`).
  - Robust execution: subprocess runs off the event loop with **one retry** on a non-zero exit → `MediaError`; a missing ffmpeg binary is detected up front via the existing `check_ffmpeg()` diagnostics and reported with a clear "install FFmpeg" message.
  - CLI `ai-video-factory compose --images output/images --audio output/audio/narration.mp3 --subtitle output/subtitles/narration.srt` → `output/video/final.mp4` + `metadata.json` (duration/fps/resolution/image_count/subtitle_count). Reads assets only — never regenerates images/audio/subtitles. 26 new tests (ffmpeg execution mocked).

### Added
- **Sprint 016 — Subtitle Generation (ADR-023):** a new `subtitle` command and transcription provider layer.
  - New `infrastructure/providers/transcription/` (mirrors the speech/image layers): `TranscriptionProvider` protocol, `GeminiTranscriptionProvider` behind a lazy-SDK `GeminiTranscriptionClient` seam (inline audio → JSON timed segments), `TranscriptionProviderFactory` (`gemini_transcription` driver), and `TranscriptionProviderSettings` (api-key falls back to the LLM key; retry ×3; default model `gemini-flash-latest`; language `vi`).
  - `to_srt()` SubRip formatter + `SubtitleStorage` (UTF-8, Vietnamese-safe).
  - CLI `ai-video-factory subtitle --audio output/audio/narration.mp3 --chapter output/chapter.json` → `output/subtitles/narration.srt`, timed to the narration; `--language` (default `vi`), `--force`, skip-if-exists, progress bar. 30 new tests (no real API).

### Added
- **Sprint 015 — Voice Generation:** the `tts` command's primary flag is now `--input` (`--chapter` kept as a backward-compatible alias); reuses the existing `SpeechProvider`, default language `vi`. Retry ×3 and skip-unless-`--force` (already present) confirmed; `output/audio/narration.mp3` + `metadata.json` unchanged. Added a `--input` unit test.

### Fixed
- **`tts` on legacy Windows (cp1252):** the Rich spinner's Braille glyphs crashed the process during synthesis — *after* `narration.mp3` was saved but *before* `metadata.json` was written, so the metadata was silently lost. The command now switches stdout to UTF-8 first, so Vietnamese narration text and progress glyphs render safely and both output files are always written.

### Added (Sprint 014)
- **Sprint 014 — Generate Real Images:** reworked the `image` command (no new architecture; provider/storage/public APIs untouched).
  - **Per-file skip**: each `NNN.png` is skipped if it already exists, unless `--force` (previously a whole-run skip).
  - **Continue on failure**: an image that fails after its retries is counted and the run continues; a final **generated / skipped / failed** summary is shown.
  - **Richer manifest** (`ImageManifestEntry`): `index, filename, prompt, provider, model, width, height, created_at`. Width/height are read from the actual PNG/JPEG bytes via a new dependency-free reader (`media/image_dimensions.py`).
  - Retry ×3 unchanged (provider `ImageRateLimiter`); each generated image is atomically renamed to its index-aligned filename.
  - Tests: new `test_image_dimensions.py`; `test_image_cli.py` reworked (generate/manifest/per-file-skip/force/continue-on-failure/retry with a mocked provider).

### Fixed
- Legacy Windows (cp1252) `UnicodeEncodeError` when printing the `image` summary — removed a non-ASCII `→` from the output.

### Added (earlier)
- **Sprint 013 — Pollinations Image Provider (ADR-022):** a free, key-less image provider for the MVP.
  - `PollinationsImageProvider` (`providers/image/pollinations/`) implementing the existing `ImageProvider` protocol, with a `PollinationsClient` seam and an httpx-backed `RealPollinationsClient` (the only module doing HTTP); no API key required.
  - Registered under the `pollinations` driver in `ImageProviderFactory`; Gemini Imagen still available via `provider=gemini_imagen`.
  - Reuses the existing `image` command unchanged (reads `output/image_prompts.json`, saves `001.png`…, manifest, retry ×3 via `ImageRateLimiter`, skip-existing unless `--force`); aspect ratio maps to width/height.
  - Added `httpx` as a direct dependency; 21 new tests (fake client + httpx `MockTransport`, no network).
  - **Default image provider changed** from `gemini_imagen` to `pollinations` (model `flux`) in settings + `.env.example` — the MVP now generates images for free with no key.

### Changed
- Default image provider is now `pollinations` (model `flux`); set `AIVF_IMAGE_PROVIDER__PROVIDER=gemini_imagen` (with a key + a Gemini image model) to use Google Imagen.

### Added (earlier)
- **Sprint 012 — Implement Image Generation (image hardening):** enhanced the existing `image` command (reuses `ImageProvider`, no refactor):
  - Images are saved as `output/images/001.png`, `002.png`, … (`ImageStorage` gained backward-compatible empty-prefix support; the default `image` prefix is unchanged, so the asset pipeline still produces `image_001.png`).
  - Writes `output/images/manifest.json` (count + per-image index/path/provider/model/generation_time) via the new `write_images_manifest`.
  - Image `retry_count` default raised 1 → 3 (transient errors are retried 3 times).
  - `image --force`; generation is skipped when `output/images/001.png` already exists unless `--force` is given.
  - 4 new tests (empty-prefix storage, manifest output, skip-without-force, `--force` regenerates); existing image CLI test updated to the `001.png` naming.
  - (Delivered after Sprint 013; the image counterpart to the tts hardening. Non-linear numbering follows the Lead's labels.)
- **Sprint 013 — Voice Generation (tts hardening):** enhanced the existing `tts` command (reuses `SpeechProvider`, no refactor):
  - `tts --force`; generation is skipped when `output/audio/narration.mp3` already exists unless `--force` is given.
  - Speech `retry_count` default raised 1 → 3 (transient errors are retried 3 times).
  - 4 new tests (settings retry-3 default, provider retry-3 behavior, skip-without-force, `--force` regenerates).
- **Sprint 011 — Asset Pipeline Foundation (ADR-021):**
  - `infrastructure/asset_pipeline/`: uniform `AssetResult` (success/path/duration/metadata); generator Protocols `ImageGenerator`, `SpeechGenerator`, `SubtitleGenerator`, `VideoComposer`; `AssetPipelineRunner` (`generate_images`/`generate_voice`/`generate_subtitles`/`compose_video`).
  - `ImageAssetGenerator` / `SpeechAssetGenerator` adapters wrap the existing image/speech providers (real, no duplication); subtitle/video are contracts only → the runner raises `AssetStageUnavailableError` until wired.
  - CLI `ai-video-factory assets` shows the pipeline status (images/voice ready; subtitles/video pending) — no generation.
  - 8 new tests (AssetResult, adapters, runner orchestration + stage status, `assets` CLI); no real API calls.
  - (Labelled "Sprint 010" by the Lead but recorded as Sprint 011, since 010 was the delivered Voice Generator.)
- **Sprint 010 — Voice Generator (ADR-020):**
  - `SpeechProvider` Protocol (`synthesize`, `health_check`, `list_voices`) with `SpeechSynthesisRequest` / `SpeechSynthesisResponse` (`infrastructure/providers/speech/base/`).
  - `GeminiSpeechProvider` over google-genai Gemini TTS behind a `GeminiTtsClient` seam (SDK lazily imported), retrying transient errors once; reuses the shared `AIProviderError`/`RetryPolicy`/`ProviderHealth`. Gemini PCM is wrapped into WAV (`pcm_to_wav`, no ffmpeg).
  - `SpeechProviderFactory.create(settings, storage)` — config-driven; speech API key falls back to the LLM key. `SpeechProviderSettings` (provider/api_key/model/voice/timeout/retry_count).
  - `AudioStorage` (`infrastructure/media/`) → `output/audio/narration.mp3`.
  - CLI `ai-video-factory tts --chapter <chapter.json>` → Rich spinner; saves `narration.mp3` + `metadata.json` (duration, voice, provider, sample_rate).
  - 23 new tests (models, audio storage + PCM→WAV, Gemini TTS provider with a fake client, factory, CLI); no real API calls.
- **Sprint 009 — Pipeline Orchestrator, Phase 1 (ADR-019):**
  - `PipelineRunner` (`infrastructure/pipeline/`) composing the existing idea/outline/chapter/image-prompt generators — sequential, persists each output immediately, stops on the first failure; one shared provider + prompt service.
  - `PipelineRequest` / `PipelineResult` typed models; progress via an injected `on_stage` callback.
  - CLI `ai-video-factory generate --topic --style --platform [--chapters]` → Rich progress (`[1/4] …`) + summary; writes `output/{ideas,story_outline,chapter,image_prompts}.json`. No image generation.
  - 3 new integration tests with a stage-aware fake provider (all outputs, stop-on-failure, `generate` CLI); no real API calls.
- **Sprint 008 — Image Provider Layer (ADR-018):**
  - `ImageProvider` Protocol (`generate`, `health_check`, `models`) with `ImageGenerationRequest` / `ImageGenerationResponse` (`infrastructure/providers/image/base/`).
  - `GeminiImagenProvider` over google-genai Imagen behind an `ImagenClient` seam (SDK lazily imported), retrying transient errors once; reuses the shared `AIProviderError`/`RetryPolicy`/`ProviderHealth`.
  - `ImageProviderFactory.create(settings, storage)` — config-driven selection; image API key falls back to the LLM key.
  - `ImageStorage` (`infrastructure/media/`) → sequential PNGs (`image_001.png`, …) in `output/images/`.
  - Configuration: `ImageProviderSettings` (provider/api_key/model/timeout/retry_count).
  - CLI `ai-video-factory image --input <image_prompts.json>` → Rich progress bar + summary; saves images.
  - 20 new tests (request/response models, storage, Imagen provider with a fake client, factory, CLI); no real API calls.
- **Sprint 007 — Image Prompt Generator (ADR-017):**
  - Domain value object `ImagePrompt` (scene_number, prompt, negative_prompt, aspect_ratio, style, camera, lighting, character_reference, environment, seed?).
  - `infrastructure/story/`: `ImagePromptGenerator` (prompt + configured `LLMProvider` via `ProviderFactory`, JSON mode, retry once), `parse_image_prompts` (injects project-level style/aspect_ratio), `ImagePromptParseError`, `read_chapter`, `write_image_prompts_json`.
  - CLI `ai-video-factory image-prompt --chapter <path> [--style --aspect-ratio --count --language]` → Rich table + `output/image_prompts.json`. Produces prompt text only — no images generated.
  - 19 new tests (image-prompt model, parser, chapter reader, generator with a fake provider, CLI); no real API calls.
- **Sprint 006 — Chapter Generator (ADR-016):**
  - Domain value object `StoryChapter` (title, content, estimated_duration_seconds).
  - `infrastructure/story/`: `ChapterGenerator` (prompt + configured `LLMProvider` via `ProviderFactory`, JSON mode, retry once), `parse_chapter` with deterministic `estimate_duration_seconds` (computed from content, not LLM-trusted), `ChapterParseError`, `read_outline`, `write_chapter_json`.
  - CLI `ai-video-factory chapter --outline <path> [--language]` → Rich chapter view + `output/chapter.json`.
  - 20 new tests (chapter model, parser/estimator, outline reader, generator with a fake provider, CLI); no real API calls.
- **Sprint 005 — Story Outline Generator (ADR-015):**
  - Domain value objects `StoryOutline` (title, genre, world_setting, cultivation_system, main_character, supporting_characters, antagonist, story_arc, ending, chapter_outlines) and `ChapterOutline` (chapter_number, title, summary, cliffhanger).
  - `infrastructure/story/`: `OutlineGenerator` (prompt + configured `LLMProvider` via `ProviderFactory`, JSON mode, parse + validate, retry once), `parse_outline` (chapter-count + required-field + non-empty validation), `OutlineParseError`, `read_idea`, `write_outline_json`.
  - CLI `ai-video-factory outline --idea <path> [--index --chapters --duration --language]` → Rich tables + `output/story_outline.json`.
  - Shared UTF-8-safe presenter helper `console_io.emit_renderable` (idea presenter reuses it).
  - 22 new tests (outline models, parser, idea reader, generator with a fake provider, CLI); no real API calls.
- **Sprint 004 — Story Idea Generator (ADR-014):**
  - Domain value objects `IdeaBrief` (topic/style/target_platform/language) and `StoryIdea` (title/hook/summary/tags).
  - `infrastructure/story/`: `IdeaGenerator` (prompt + configured `LLMProvider` via `ProviderFactory`, JSON mode, parse + validate, retry once), `parse_ideas`, `IdeaParseError`, `write_ideas_json`.
  - CLI `ai-video-factory idea --topic --style --platform [--language]` → Rich table + `output/ideas.json`.
  - 17 new tests (models, parser, generator with a fake provider, CLI); no real API calls.
- **Sprint 003 — Prompt Engine (ADR-013):**
  - `infrastructure/prompts/`: `PromptLoader` (load + cache + `PromptNotFoundError`), `PromptRenderer` (Jinja2, `StrictUndefined`), `PromptValidator` (exists + syntax + required variables), `PromptService` (`render`, `validate`, `list_prompts`).
  - Prompt error hierarchy: `PromptError → PromptNotFoundError`, `PromptValidationError`, `PromptRenderError`.
  - Prompt templates under the configurable root `prompts/`: `story/idea.md`, `story/outline.md`, `story/chapter.md`, `story/scene.md`, `image/image_prompt.md` — no prompt text in Python.
  - Configuration: `PromptSettings.root` (default `prompts/`, env `AIVF_PROMPTS__ROOT`); `jinja2` runtime dependency.
  - CLI: `factory prompt list`, `prompt show <name>`, `prompt validate`, `prompt render <name> --var k=v` (UTF-8-safe raw output).
  - 26 new tests (loader, renderer, validator, service incl. shipped templates, CLI).
- **Sprint 002 — AI Provider Layer:** the single, vendor-neutral way the system talks to LLM providers (ADR-012).
  - `LLMProvider` Protocol (`generate`, `health_check`, `count_tokens`, `models`) with strongly typed `LLMRequest`, `LLMResponse`, `TokenUsage`, `RawCompletion`, `ProviderHealth`.
  - Provider error hierarchy: `AIProviderError` → `AuthenticationError`, `RateLimitError`, `TimeoutError`, `ProviderUnavailableError`, `InvalidResponseError` (extends the existing `ProviderError` tree).
  - `RetryPolicy` — exponential backoff retrying only 429/503/timeout; configurable per-request timeout.
  - `GeminiProvider` (first provider) over the official `google-genai` SDK, isolated behind a `GeminiClient` seam (SDK lazily imported); API key read from settings.
  - `ProviderFactory.create()` — config-driven provider selection.
  - `ProviderSettings` (`provider`, `api_key` as `SecretStr`, `model`, `timeout`, `retry_count`); `google-genai` runtime dependency.
  - `doctor` now checks the AI provider (API key configured + reachable), reporting OK/WARN/FAIL; diagnostics status is tri-state via `shared/health.HealthStatus`.
  - 35 new tests (models, errors, retry, Gemini via a fake client, factory) — no real API calls.
- **Sprint 001.5 — Foundation Review Fix:**
  - `.editorconfig` (UTF-8, LF, 4-space indent, trim trailing whitespace, final newline; Markdown/Makefile/YAML overrides).
  - `Makefile` targets: `install`, `sync`, `lint`, `format`, `typecheck`, `test`, `doctor`, `run`, `clean`, `hooks`.
  - `.pre-commit-config.yaml` with ruff check, ruff format, mypy, and a manual-stage pytest hook (local hooks via `uv run`); `pre-commit` added to dev extras.
  - `.gitkeep` placeholders for `logs/`, `output/`, `data/`.
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
- `prompts/story/idea.md` rewritten to generate multiple story ideas as JSON (variables `topic, style, target_platform, language, count`); two Sprint 003 prompt tests updated to match.
- `prompts/story/outline.md` rewritten to generate a full `StoryOutline` as JSON (variables `idea_title, idea_hook, idea_summary, target_duration, chapter_count, language`).
- `prompts/story/chapter.md` rewritten to generate narration prose as JSON `{title, content}` from the outline fields.
- `prompts/image/image_prompt.md` rewritten to generate a JSON `{image_prompts:[…]}` array of cinematic image prompts from the chapter (variables `chapter_title, chapter_content, style, aspect_ratio, count, language`).

### Deprecated
- _None._

### Removed
- _None._

### Fixed
- Story generators no longer fail with "provider returned invalid JSON" on thinking-capable models: raised `max_output_tokens` to 8192 for the idea/outline/chapter/image-prompt generators (a small cap truncated the JSON), and added lenient JSON parsing (`json_extract.loads_json`) that tolerates Markdown code fences.
- Chapter generation robustness: the chapter prompt now asks for a bounded ~180–300 word short-video narration (previously "the complete story", which overran the token budget and truncated the JSON); the chapter parser tolerates unescaped control characters (long-prose newlines, `strict=False`) and double-encoded JSON, and surfaces the actual `JSONDecodeError` detail instead of a generic message; the raw model response is logged and saved to `output/debug/chapter_raw_response.txt` for diagnosis.
- Tests are now isolated from a local `.env` file (which may hold a real API key), so no test can accidentally hit a live provider.

### Changed
- Expanded `.gitignore` (tooling caches, virtualenvs, coverage, logs, `output/*` and `data/*` with `.gitkeep` negations, `.env`, IDE/OS files).
- Rewrote `CLAUDE.md` to define project role, architecture rules, sprint rules, coding rules, and review rules.

### Removed
- Runtime artifacts removed from the working tree (`__pycache__`, `*.pyc`, `*.db`, `*.sqlite`, log files); the `logs/`, `output/`, and `data/` folders are preserved via `.gitkeep`.

### Fixed
- CLI raw text output (`prompt show`/`prompt render`) no longer crashes on legacy Windows (cp1252) consoles when the content contains non-ASCII characters (e.g. Vietnamese, Chinese); it is now written as UTF-8 bytes.

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
