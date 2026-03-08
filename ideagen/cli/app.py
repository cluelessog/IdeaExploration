"""IdeaGen CLI application."""

import typer
from rich.console import Console

from ideagen import __version__

app = typer.Typer(
    name="ideagen",
    help="Automated idea generation framework — scrape, analyze, synthesize.",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"ideagen {__version__}")
        raise typer.Exit()


@app.callback()
def _callback(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """IdeaGen — Automated idea generation from trending data."""


from ideagen.cli.commands.run import run_app
from ideagen.cli.commands.sources_cmd import sources_app
from ideagen.cli.commands.config_cmd import config_app
from ideagen.cli.commands.history import history_app
from ideagen.cli.commands.interactive import interactive_app
from ideagen.cli.commands.schedule import schedule_app

app.add_typer(run_app, name="run")
app.add_typer(sources_app, name="sources")
app.add_typer(config_app, name="config")
app.add_typer(history_app, name="history")
app.add_typer(interactive_app, name="interactive")
app.add_typer(schedule_app, name="schedule")


def main() -> None:
    app()
