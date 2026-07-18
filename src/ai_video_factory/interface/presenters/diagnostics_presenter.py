"""Terminal presenter for diagnostics output (interface layer)."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from ai_video_factory.infrastructure.diagnostics import CheckResult


def render_diagnostics(results: list[CheckResult], *, console: Console | None = None) -> None:
    """Render diagnostic results as a Rich table.

    Args:
        results: The diagnostic outcomes to display.
        console: Optional console to render to; a default one is used if omitted.
    """
    out = console or Console()
    table = Table(title="AI Video Factory - Doctor")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail", overflow="fold")
    for result in results:
        status = "[green]OK[/green]" if result.ok else "[red]FAIL[/red]"
        table.add_row(result.name, status, result.detail)
    out.print(table)
