from __future__ import annotations
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

history_app = typer.Typer(name="history", help="Browse past runs.")
console = Console()


@history_app.command("list")
def list_runs(
    offset: int = typer.Option(0, "--offset"),
    limit: int = typer.Option(20, "--limit"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Show past runs."""
    from ideagen.cli.async_bridge import run_async
    from ideagen.cli.config_loader import load_config
    from ideagen.storage.sqlite import SQLiteStorage

    config = load_config(config_path)
    storage = SQLiteStorage(db_path=config.storage.database_path)

    runs = run_async(storage.get_runs(offset=offset, limit=limit))

    if not runs:
        console.print("[yellow]No runs found.[/yellow]")
        return

    table = Table(title="Past Runs")
    table.add_column("ID", style="dim", max_width=8)
    table.add_column("Timestamp", style="cyan")
    table.add_column("Domain", style="green")
    table.add_column("Ideas", style="yellow")
    table.add_column("Sources", style="blue")

    for run in runs:
        table.add_row(
            run["id"][:8],
            run["timestamp"][:19],
            run["domain"],
            str(run["ideas_count"]),
            run.get("sources_used", "[]"),
        )

    console.print(table)


@history_app.command("prune")
def prune_history(
    older_than: str = typer.Option(..., "--older-than", help="Delete runs older than (e.g. '30d')"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Delete old runs."""
    from ideagen.cli.async_bridge import run_async
    from ideagen.cli.config_loader import load_config
    from ideagen.storage.sqlite import SQLiteStorage

    days = int(older_than.rstrip("d"))
    config = load_config(config_path)
    storage = SQLiteStorage(db_path=config.storage.database_path)

    count = run_async(storage.delete_runs_older_than(days))
    console.print(f"[green]Deleted {count} runs older than {days} days.[/green]")
