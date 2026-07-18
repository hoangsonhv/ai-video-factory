# 08 — ENVIRONMENT

**Purpose:** The definitive guide to setting up a development environment that can build, test, and run AI Video Factory. It gets a new contributor from a clean machine to a green test run and a working `factory` CLI.

**Owner:** Technical Lead.

**When to update:** When a dependency, tool, minimum version, environment variable, or setup step changes. Must stay consistent with `04_DECISIONS.md` (stack) and `05_CONVENTIONS.md` (tooling).

---

## Sections

1. Prerequisites
2. System Dependencies
3. Project Setup
4. Configuration & Secrets
5. Environment Variables
6. Running the CLI
7. Running Tests & Quality Gates
8. Database & Migrations
9. Directory Layout
10. Troubleshooting

---

## 1. Prerequisites

| Tool | Minimum | Notes |
|---|---|---|
| Python | 3.13 | Async-first codebase (ADR-002) |
| ffmpeg | recent stable | Required for the Video stage (`FfmpegVideoComposer`) |
| Git | any recent | Version control |
| A virtual env manager | `venv` (builtin) or `uv`/`poetry` | Isolate dependencies |

No Docker is required or used (ADR: non-goal). No database server is needed — SQLite is embedded (ADR-003).

## 2. System Dependencies

- **ffmpeg** must be on `PATH`. Verify: `ffmpeg -version`.
  - Windows: install a static build and add its `bin/` to `PATH`.
  - macOS: `brew install ffmpeg`.
  - Linux: use the distro package or a static build.
- **Python 3.13**: verify `python --version` reports 3.13.x.

## 3. Project Setup

```bash
# from the repository root: D:\project\ai-video-factory
python -m venv .venv
# activate:
#   Windows (PowerShell):  .venv\Scripts\Activate.ps1
#   macOS/Linux:           source .venv/bin/activate

pip install -e ".[dev]"     # installs runtime + dev tooling (ruff, mypy/pyright, pytest, import-linter)
```

> The exact dependency set is defined by the project's packaging file. `[dev]` includes all quality-gate tooling from `05_CONVENTIONS.md`.

## 4. Configuration & Secrets

- Copy the example config to a local file and adjust:
  ```
  config/config.example.toml → config/config.toml
  ```
- Secrets (API keys) are **never** committed. Provide them via environment variables or a local secrets file that is git-ignored.
- Provider selection is via `driver` keys (see `07_WORKFLOW.md` / ADR-005). Example:
  ```toml
  [providers.story]
  driver = "openai"
  prompt_version = "v1"

  [providers.image]
  driver = "replicate"

  [providers.voice]
  driver = "elevenlabs"

  [providers.subtitle]
  driver = "whisper"

  [database]
  url = "sqlite:///./data/factory.db"

  [pipeline]
  max_concurrent_scenes = 3
  ```
- The full settings tree is validated at startup; an invalid or unknown `driver` fails fast with `ConfigurationError` (ADR-008).

## 5. Environment Variables

| Variable | Purpose | Example |
|---|---|---|
| `APP_ENV` | Select environment/config file (`dev`/`test`/`prod`) | `dev` |
| `OPENAI_API_KEY` | Story/Scene provider secret | `sk-...` |
| `REPLICATE_API_TOKEN` | Image provider secret | `r8_...` |
| `ELEVENLABS_API_KEY` | Voice provider secret | `...` |
| `LOG_LEVEL` | Override log level | `DEBUG` |

- Secrets are loaded only by the config loader into `SecretStr`; no other module reads `os.environ` (ADR-008, `05_CONVENTIONS.md`).
- Variable names above are examples matching the planned adapters; the authoritative list is the config settings tree.

## 6. Running the CLI

```bash
factory status
factory generate --idea "A lighthouse keeper who befriends a storm" --lang en
factory resume <project_id>
factory render <project_id>
```

Add `--verbose` to surface full tracebacks (default output is clean, operator-friendly).

## 7. Running Tests & Quality Gates

```bash
ruff check .            # lint
ruff format --check .   # format check
mypy --strict .         # (or: pyright)  static typing
lint-imports            # import-linter — layer boundary contracts
pytest                  # full test suite (no paid APIs by default)
pytest -m "not live"    # explicitly skip opt-in live-provider tests
```

All of the above run in CI as blocking gates. Run them locally before opening a PR.

## 8. Database & Migrations

```bash
alembic upgrade head        # apply migrations (creates SQLite schema)
alembic revision -m "..."   # create a new migration after model changes
```

- The SQLite file lives at the `database.url` path (default `./data/factory.db`).
- Tests use a temporary/in-memory SQLite database; they never touch your dev DB.

## 9. Directory Layout

```
ai-video-factory/
├── src/ai_video_factory/ # source, Clean Architecture layers (ADR-011)
├── data/                 # SQLite db, git-ignored
├── logs/                 # rotating log files, git-ignored
├── output/               # rendered MP4s, git-ignored
├── docs/                 # this documentation set
├── tests/
├── .env.example          # copy to .env (git-ignored) and adjust
└── pyproject.toml
```

`data/`, `logs/`, `output/`, and `.env` are git-ignored. Environment-driven
configuration uses the `AIVF_` prefix with `__` nesting (see `.env.example`).

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ConfigurationError` at startup | Missing/invalid config or unknown `driver` | Check `config.toml` and env vars |
| Video stage fails with `MediaError` | ffmpeg not on `PATH` or bad inputs | `ffmpeg -version`; inspect stage logs |
| Provider `429`/timeouts | Rate limit | Lower `max_concurrent_scenes`; retries are automatic for retryable errors |
| `lint-imports` fails | Layer boundary violated | Remove the outward import; wire via the composition root |
| Secrets appear missing | Not exported / wrong `APP_ENV` | Export the env var; confirm the active config file |
| Run restarts from scratch | Using a new project id instead of resume | Use `factory resume <project_id>` |
