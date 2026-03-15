from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

schedule_app = typer.Typer(name="schedule", help="Schedule recurring idea generation.")
console = Console()


@schedule_app.command("add")
def add_schedule(
    daily: bool = typer.Option(False, "--daily"),
    weekly: bool = typer.Option(False, "--weekly"),
    time: str = typer.Option("09:00", "--time", "-t"),
    domain: str = typer.Option("software", "--domain", "-d"),
    config_path: Optional[Path] = typer.Option(None, "--schedule-file", help="Custom schedule file path"),
) -> None:
    """Create a new generation schedule."""
    from ideagen.cli.schedule_store import install_cron, save_schedule

    if daily and weekly:
        typer.echo("Error: --daily and --weekly are mutually exclusive. Specify only one.", err=True)
        raise typer.Exit(code=1)
    if not daily and not weekly:
        typer.echo("Error: Specify a frequency with --daily or --weekly.", err=True)
        raise typer.Exit(code=1)

    frequency = "weekly" if weekly else "daily"
    schedule = {"frequency": frequency, "time": time, "domain": domain}

    schedule_id = save_schedule(schedule, path=config_path)
    console.print(f"[green]Schedule '{schedule_id}' created: {frequency} at {time} for {domain} domain[/green]")

    if sys.platform == "win32":
        console.print("[yellow]Cron is not available on Windows. Run manually or use Task Scheduler.[/yellow]")
        console.print(f"  Command: ideagen run --domain {domain}")
    else:
        schedule["id"] = schedule_id  # ensure id is set for cron install
        if install_cron(schedule):
            console.print("[green]Cron job installed.[/green]")
        else:
            console.print("[yellow]Could not install cron job. You may need to set it up manually.[/yellow]")


@schedule_app.command("list")
def list_schedules(
    config_path: Optional[Path] = typer.Option(None, "--schedule-file", help="Custom schedule file path"),
) -> None:
    """Show active schedules."""
    from ideagen.cli.schedule_store import load_schedules

    schedules = load_schedules(path=config_path)

    if not schedules:
        console.print("[yellow]No active schedules. Use 'schedule add' to create one.[/yellow]")
        return

    table = Table(title="Active Schedules")
    table.add_column("ID", style="dim")
    table.add_column("Frequency", style="cyan")
    table.add_column("Time", style="green")
    table.add_column("Domain", style="yellow")
    table.add_column("Created", style="dim")

    for s in schedules:
        table.add_row(
            s.get("id", "?"),
            s.get("frequency", "?"),
            s.get("time", "?"),
            s.get("domain", "?"),
            s.get("created_at", "?")[:19],
        )

    console.print(table)


@schedule_app.command("remove")
def remove_schedule_cmd(
    schedule_id: str = typer.Argument(..., help="Schedule ID to remove"),
    config_path: Optional[Path] = typer.Option(None, "--schedule-file", help="Custom schedule file path"),
) -> None:
    """Remove a schedule."""
    from ideagen.cli.schedule_store import remove_schedule, uninstall_cron

    removed = remove_schedule(schedule_id, path=config_path)

    if not removed:
        console.print(f"[red]Schedule '{schedule_id}' not found.[/red]")
        raise typer.Exit(code=1)

    uninstall_cron(schedule_id)
    console.print(f"[green]Schedule '{schedule_id}' removed.[/green]")
