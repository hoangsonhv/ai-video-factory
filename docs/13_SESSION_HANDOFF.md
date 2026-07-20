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
**Sprint:** 017 — Video Composer (delivered)
**Version:** 0.1.0-dev
**Branch:** `feat/sprint017-video-composer`

### What was accomplished this session
- New self-contained **`infrastructure/video/`** package (ffmpeg-only): pure `build_ffmpeg_command()` (argv generator), `parse_srt_cues()` (subtitle timing), `FfmpegVideoComposer` (**satisfies the existing `VideoComposer` protocol** in `asset_pipeline/generators.py` — no new port, no factory), `write_video_metadata`.
- Composition: 1080x1920/30fps/H.264/AAC; one image per subtitle cue, **reuse last image** when images < cues; per-image Ken Burns `zoompan`; `xfade` crossfades (cumulative offsets); burned subtitles (`subtitles` filter, Windows-escaped path); narration audio `-shortest`. Ken Burns constants live in `ffmpeg_command.py`; encoding params in `VideoSettings`.
- Robust exec: subprocess off the event loop (`asyncio.to_thread`, **injectable runner** — mocked in tests); **retry once** on non-zero → `MediaError`; missing binary → `MediaError`. The CLI **verifies ffmpeg with the existing `check_ffmpeg()`** before composing and prints a clear install message if absent.
- CLI `compose --images --audio --subtitle` registered in `app.py`: reads assets only (never regenerates), writes `output/video/final.mp4` + `metadata.json`.
- ADR-024 recorded; `VideoSettings` + `.env.example` video section added.
- Tests: 26 new (command gen, srt timing, composer retry/missing-ffmpeg/reuse-last/errors, CLI, settings) — **ffmpeg fully mocked**. 353 pass.
- ffmpeg is **not installed** on this machine (expected) → `compose` exits 1 with a friendly "install FFmpeg" message (verified). Operator will install ffmpeg and run the live compose.

### Current in-flight work
- None. Sprint 017 complete; live ffmpeg render pending the operator's local ffmpeg install.

### Next Action (do this first)
> Wait for the next Sprint specification from the Lead. The **subtitle** stage and the **video composition** stage (needs ffmpeg) plug into the asset pipeline by implementing `SubtitleGenerator` / `VideoComposer` and injecting them into `AssetPipelineRunner`. Do NOT build them until specified.

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
- **Testing:** inject a fake `GeminiTtsClient`/`SpeechProvider`; `asyncio.run`; no real API. The skip test needs no mock (skip returns before building the provider).
- **Tooling:** `uv`; `make lint/format/typecheck/test`. Console script `ai-video-factory`.

### Decisions made this session
- Added ADR-024 — an **ffmpeg VideoComposer** that satisfies the existing `VideoComposer` protocol (no new port, no factory — a single ffmpeg backend, avoiding a placeholder abstraction). Command generation is a **pure** function (unit-tested without ffmpeg); the subprocess runner is injectable (mocked in tests).
- Verified ffmpeg with the existing `check_ffmpeg()` diagnostics before composing; missing ffmpeg → clear message + exit 1 (and `MediaError` at the runner level).
- Kept the video package self-contained in `infrastructure/video/`; did not touch the asset pipeline or any other provider (respecting "do not refactor unrelated modules").

### Open questions / risks for next session
- **Live ffmpeg render not yet run** — ffmpeg isn't installed on this machine (expected). The operator will install it and run `compose`. The filter graph (zoompan + xfade offsets + subtitles path escaping) may need small tuning once validated against real ffmpeg output.
- Crossfades overlap subtitle cue windows slightly (small fades) → minor timing approximation; `-shortest` trims video to the narration.
- The `default_ffmpeg_runner` real subprocess path is exercised only via the missing-binary case; a fixture-based integration test needs ffmpeg (per ai-tool.md testing strategy).

### Files touched this session
- New source: `infrastructure/video/{__init__,srt_timing,ffmpeg_command,ffmpeg_composer,writer}.py`, `interface/cli/compose_commands.py`, `interface/presenters/video_presenter.py`.
- Modified source: `config/settings.py` (+`VideoSettings`, wired into `Settings`), `interface/cli/app.py` (register `compose`).
- Config: `.env.example` (+video section).
- Tests: new `test_ffmpeg_command.py`, `test_srt_timing.py`, `test_ffmpeg_composer.py`, `test_compose_cli.py`; `test_settings.py` (+video defaults).
- Docs: `04_DECISIONS.md` (ADR-024), `12_PROJECT_STATE.md`, `13_SESSION_HANDOFF.md`, `CHANGELOG.md`. Architecture doc (`ai-tool.md`) untouched.
- Also this session (separate ask): fixed the two long-standing LLM-default test assertions (`gemini-2.0-flash` → `gemini-3.5-flash`) — suite is fully green.

### Do NOT do
- Do not add a Web UI, FastAPI, or Docker (ADR-001, ADR-004; non-goals).
- Do not put I/O or vendor code in `domain/`.
- Do not regenerate images/audio/subtitles; do not implement upload — future sprints.

---

## Handoff History (rolling, newest first)

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
