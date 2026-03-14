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


@history_app.command("show")
def show_run(
    run_id: str = typer.Argument(..., help="Run ID or prefix (first 8+ chars)"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Show details of a specific run."""
    from ideagen.cli.async_bridge import run_async
    from ideagen.cli.config_loader import load_config
    from ideagen.cli.formatters import format_idea_card
    from ideagen.storage.sqlite import SQLiteStorage

    config = load_config(config_path)
    storage = SQLiteStorage(db_path=config.storage.database_path)

    # Check for prefix ambiguity
    matches = run_async(storage.find_runs_by_prefix(run_id))
    if not matches:
        console.print(f"[red]No run found matching '{run_id}'[/red]")
        raise typer.Exit(code=1)

    if len(matches) > 1:
        console.print(f"[yellow]Ambiguous prefix '{run_id}' matches {len(matches)} runs. Showing most recent. Use a longer prefix to be specific.[/yellow]")
        match_table = Table(title="Matching Runs")
        match_table.add_column("ID", style="dim", max_width=12)
        match_table.add_column("Timestamp", style="cyan")
        match_table.add_column("Domain", style="green")
        for m in matches[:5]:
            match_table.add_row(m["id"][:12], str(m.get("timestamp", ""))[:19], m.get("domain", ""))
        console.print(match_table)

    # Use the most recent match (first in list, ordered by timestamp DESC)
    detail = run_async(storage.get_run_detail(matches[0]["id"]))

    if detail is None:
        console.print(f"[red]No run found matching '{run_id}'[/red]")
        raise typer.Exit(code=1)

    # Run metadata table
    import json
    table = Table(title=f"Run {detail['id'][:8]}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("ID", detail["id"])
    table.add_row("Timestamp", detail["timestamp"][:19])
    table.add_row("Domain", detail["domain"])
    table.add_row("Sources", detail.get("sources_used", "[]"))
    table.add_row("Items Scraped", str(detail["total_items_scraped"]))
    table.add_row("After Dedup", str(detail["total_after_dedup"]))
    table.add_row("Ideas", str(detail["ideas_count"]))
    console.print(table)

    # Idea cards
    for report in detail.get("ideas", []):
        console.print(format_idea_card(report))


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
