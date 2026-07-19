"""``factory prompt`` CLI command group (interface layer).

Thin commands: build the prompt service from settings, invoke it, present the
result. All prompt text and logic live in the infrastructure prompt engine.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from ai_video_factory.infrastructure.config.settings import load_settings
from ai_video_factory.infrastructure.prompts.errors import PromptError
from ai_video_factory.infrastructure.prompts.service import PromptService
from ai_video_factory.interface.presenters.prompt_presenter import (
    render_prompt_names,
    render_text,
    render_validation_rows,
)

prompt_app = typer.Typer(no_args_is_help=True, help="Inspect and render prompt templates.")
_console = Console()


def _service() -> PromptService:
    return PromptService.create(load_settings().prompts.root)


def _parse_vars(pairs: list[str]) -> dict[str, str]:
    variables: dict[str, str] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key.strip():
            raise typer.BadParameter(f"expected key=value, got {pair!r}", param_hint="--var")
        variables[key.strip()] = value
    return variables


@prompt_app.command("list")
def list_prompts_command() -> None:
    """List every available prompt template."""
    render_prompt_names(_service().list_prompts(), console=_console)


@prompt_app.command("show")
def show_prompt_command(
    name: Annotated[str, typer.Argument(help="Prompt name, e.g. story/idea")],
) -> None:
    """Print the raw template text of a prompt."""
    try:
        render_text(_service().load(name), console=_console)
    except PromptError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@prompt_app.command("validate")
def validate_prompts_command() -> None:
    """Validate every prompt template; exit non-zero if any is invalid."""
    service = _service()
    rows: list[tuple[str, bool, str]] = []
    for name in service.list_prompts():
        try:
            result = service.validate(name)
            if result.required_variables:
                detail = "vars: " + ", ".join(result.required_variables)
            else:
                detail = "no variables"
            rows.append((name, True, detail))
        except PromptError as exc:
            rows.append((name, False, str(exc)))
    render_validation_rows(rows, console=_console)
    if any(not ok for _, ok, _ in rows):
        raise typer.Exit(code=1)


@prompt_app.command("render")
def render_prompt_command(
    name: Annotated[str, typer.Argument(help="Prompt name, e.g. story/idea")],
    var: Annotated[
        list[str] | None,
        typer.Option("--var", help="Template variable as key=value (repeatable)."),
    ] = None,
) -> None:
    """Render a prompt with the given variables and print the result."""
    variables = _parse_vars(var or [])
    try:
        render_text(_service().render(name, variables), console=_console)
    except PromptError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
