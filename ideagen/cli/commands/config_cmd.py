from __future__ import annotations
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.syntax import Syntax

config_app = typer.Typer(name="config", help="Manage configuration.")
console = Console()


@config_app.command("show")
def show_config(
    config_path: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Display current configuration."""
    from ideagen.cli.config_loader import load_config
    config = load_config(config_path)
    data = config.model_dump(mode="json")

    # Redact optional API keys
    if data.get("providers", {}).get("openai_api_key"):
        data["providers"]["openai_api_key"] = "***REDACTED***"
    if data.get("providers", {}).get("gemini_api_key"):
        data["providers"]["gemini_api_key"] = "***REDACTED***"

    import json
    syntax = Syntax(json.dumps(data, indent=2), "json", theme="monokai")
    console.print(syntax)


@config_app.command("init")
def init_config(
    config_path: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Create default configuration file."""
    from ideagen.cli.config_loader import save_config
    from ideagen.core.config import IdeaGenConfig

    path = save_config(IdeaGenConfig(), config_path)
    console.print(f"[green]Config created at {path}[/green]")
