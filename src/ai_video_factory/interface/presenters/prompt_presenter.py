"""Terminal presenters for the ``prompt`` CLI commands (interface layer)."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.table import Table


def render_prompt_names(names: list[str], *, console: Console) -> None:
    """Print the list of available prompt names."""
    if not names:
        console.print("No prompts found.")
        return
    table = Table(title="Prompts")
    table.add_column("Name", style="bold")
    for name in names:
        table.add_row(name)
    console.print(table)


def render_text(text: str, *, console: Console) -> None:
    """Print raw prompt/rendered text verbatim.

    Prompt content is international (e.g. Vietnamese, Chinese), so it is written
    as UTF-8 bytes directly to the stdout buffer rather than through Rich's
    console encoder, which raises on legacy (cp1252) Windows terminals.
    """
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:  # exotic stream without a byte buffer
        console.print(text, markup=False, highlight=False)
        return
    payload = text if text.endswith("\n") else text + "\n"
    buffer.write(payload.encode("utf-8", errors="backslashreplace"))
    buffer.flush()


def render_validation_rows(rows: list[tuple[str, bool, str]], *, console: Console) -> None:
    """Print a validation table of (name, ok, detail) rows."""
    table = Table(title="Prompt Validation")
    table.add_column("Prompt", style="bold")
    table.add_column("Status")
    table.add_column("Detail", overflow="fold")
    for name, ok, detail in rows:
        status = "[green]OK[/green]" if ok else "[red]INVALID[/red]"
        table.add_row(name, status, detail)
    console.print(table)
