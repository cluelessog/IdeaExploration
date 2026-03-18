"""Dashboard CLI command — starts the web server."""
from __future__ import annotations

from typing import Optional

import typer

dashboard_app = typer.Typer(name="dashboard", help="Start the web dashboard.")


@dashboard_app.callback(invoke_without_command=True)
def dashboard(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind address"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port"),
) -> None:
    """Start the IdeaGen web dashboard."""
    try:
        import uvicorn
    except ImportError:
        typer.echo(
            "Web dependencies not installed. Run: pip install -e '.[web]'",
            err=True,
        )
        raise typer.Exit(code=1)

    from ideagen.web.app import create_app

    app = create_app()
    uvicorn.run(app, host=host, port=port)
