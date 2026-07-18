# AI Video Factory

CLI-first, automated AI video generation pipeline (Idea → Story → Scene → Image
→ Voice → Subtitle → Video → MP4).

The full documentation lives in [`docs/`](docs/); start with
[`docs/12_PROJECT_STATE.md`](docs/12_PROJECT_STATE.md) (the single source of
truth) and the architecture in [`docs/ai-tool.md`](docs/ai-tool.md).

## Quick start

```bash
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# macOS/Linux:          source .venv/bin/activate

pip install -e ".[dev]"

factory version
factory doctor
```

Configuration is environment-driven; copy `.env.example` to `.env` and adjust.

## Quality gates

```bash
ruff check .
ruff format --check .
mypy src
pytest
```
