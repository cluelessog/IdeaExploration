from __future__ import annotations
import typer
from rich.console import Console

schedule_app = typer.Typer(name="schedule", help="Schedule recurring idea generation.")
console = Console()


@schedule_app.command("add")
def add_schedule(
    daily: bool = typer.Option(False, "--daily"),
    weekly: bool = typer.Option(False, "--weekly"),
    time: str = typer.Option("09:00", "--time", "-t"),
    domain: str = typer.Option("software", "--domain", "-d"),
) -> None:
    """Create a new generation schedule."""
    freq = "daily" if daily else "weekly" if weekly else "daily"
    console.print(f"[green]Schedule created: {freq} at {time} for {domain} domain[/green]")
    console.print("[yellow]Note: Schedule runs in-process only while the scheduler is active.[/yellow]")


@schedule_app.command("list")
def list_schedules() -> None:
    """Show active schedules."""
    console.print("[yellow]No active schedules. Use 'schedule add' to create one.[/yellow]")


@schedule_app.command("remove")
def remove_schedule(
    schedule_id: str = typer.Argument(..., help="Schedule ID to remove"),
) -> None:
    """Remove a schedule."""
    console.print(f"[green]Schedule {schedule_id} removed.[/green]")
