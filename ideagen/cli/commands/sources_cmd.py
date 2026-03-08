from __future__ import annotations
import typer
from rich.console import Console
from rich.table import Table

sources_app = typer.Typer(name="sources", help="Manage data sources.")
console = Console()


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
