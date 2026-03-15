from __future__ import annotations
from typing import Optional
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

compare_app = typer.Typer(name="compare", help="Compare two runs.")
console = Console()


@compare_app.callback(invoke_without_command=True)
def compare_runs_cmd(
    run1: str = typer.Argument(..., help="First run ID or prefix"),
    run2: str = typer.Argument(..., help="Second run ID or prefix"),
    threshold: float = typer.Option(0.85, "--threshold", "-t", help="Fuzzy match threshold (0-1)"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Compare two runs and show differences."""
    from ideagen.cli.async_bridge import run_async
    from ideagen.cli.config_loader import load_config
    from ideagen.storage.sqlite import SQLiteStorage
    from ideagen.core.comparison import compare_runs

    config = load_config(config_path)
    storage = SQLiteStorage(db_path=config.storage.database_path)

    def resolve_run(prefix: str) -> "dict | None":
        matches = run_async(storage.find_runs_by_prefix(prefix))
        if not matches:
            console.print(f"[red]No run found matching '{prefix}'[/red]")
            return None
        if len(matches) > 1:
            console.print(
                f"[yellow]Ambiguous prefix '{prefix}' matches {len(matches)} runs. "
                f"Using most recent: {matches[0]['id'][:12]}... "
                f"Use a longer prefix to be specific.[/yellow]"
            )
        return run_async(storage.get_run_detail(matches[0]["id"]))

    detail_a = resolve_run(run1)
    detail_b = resolve_run(run2)

    if detail_a is None:
        raise typer.Exit(code=1)
    if detail_b is None:
        raise typer.Exit(code=1)

    result = compare_runs(detail_a, detail_b, threshold=threshold)

    # Display results
    table = Table(title=f"Comparison: {run1[:8]} vs {run2[:8]}")
    table.add_column("Status", style="bold")
    table.add_column("Idea")
    table.add_column("Detail")

    for title in result.added:
        table.add_row("[green]Added[/green]", title, "New in second run")
    for title in result.removed:
        table.add_row("[red]Removed[/red]", title, "Missing from second run")
    for ta, tb in result.common:
        label = f"{ta}" if ta == tb else f"{ta} → {tb}"
        table.add_row("[dim]Common[/dim]", label, "")
    for sc in result.score_changes:
        table.add_row(
            "[yellow]Score Δ[/yellow]",
            sc["title_b"],
            f"{sc['score_a']:.1f} → {sc['score_b']:.1f}",
        )

    console.print(table)

    if not result.added and not result.removed and not result.score_changes:
        console.print("[green]Runs are identical.[/green]")
