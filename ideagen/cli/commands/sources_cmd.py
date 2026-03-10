from __future__ import annotations
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

sources_app = typer.Typer(name="sources", help="Manage data sources.")
console = Console()


@sources_app.command("list")
def list_sources(
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config file"),
) -> None:
    """Show all available data sources and their enabled/disabled status."""
    from ideagen.cli.config_loader import load_config
    from ideagen.sources.registry import get_available_source_names

    config = load_config(config_path)
    enabled = config.sources.enabled

    all_names = get_available_source_names()

    table = Table(title="Data Sources")
    table.add_column("Source", style="cyan")
    table.add_column("Status")

    for name in all_names:
        if name in enabled:
            table.add_row(name, "[green]enabled[/green]")
        else:
            table.add_row(name, "[dim]disabled[/dim]")

    console.print(table)


@sources_app.command("test")
def test_sources() -> None:
    """Health check all data sources."""
    from ideagen.cli.async_bridge import run_async
    from ideagen.sources.registry import get_all_sources

    sources = get_all_sources()
    table = Table(title="Source Health Check")
    table.add_column("Source", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Version", style="dim")

    async def _check():
        for name, source in sources.items():
            try:
                available = await source.is_available()
                status = "[green]OK[/green]" if available else "[red]UNAVAILABLE[/red]"
            except Exception as e:
                status = f"[red]ERROR: {e}[/red]"
            table.add_row(name, status, source.PARSER_VERSION)

    run_async(_check())
    console.print(table)
