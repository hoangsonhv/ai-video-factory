.PHONY: help install sync lint format typecheck test doctor run clean hooks

help: ## Show available targets
	@echo "Targets: install sync lint format typecheck test doctor run clean hooks"

install: ## Install the project with dev dependencies (editable)
	uv pip install -e ".[dev]"

sync: ## Sync the environment from pyproject (incl. dev extras)
	uv sync --extra dev

lint: ## Run Ruff lint checks
	uv run ruff check .

format: ## Format the codebase with Ruff
	uv run ruff format .

typecheck: ## Run MyPy (strict) on the package
	uv run mypy src

test: ## Run the test suite
	uv run pytest

doctor: ## Run environment diagnostics
	uv run factory doctor

run: ## Run the CLI (shows available commands)
	uv run factory --help

hooks: ## Install pre-commit git hooks
	uv run pre-commit install

clean: ## Remove caches and runtime artifacts (folders preserved)
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -path ./.venv -prune -o -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -path ./.venv -prune -o -type f -name '*.py[cod]' -delete 2>/dev/null || true
	find logs -type f -name '*.log' -delete 2>/dev/null || true
	find output -type f ! -name '.gitkeep' -delete 2>/dev/null || true
	find data -type f \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \) -delete 2>/dev/null || true
