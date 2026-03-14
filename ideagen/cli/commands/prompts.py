from __future__ import annotations
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

prompts_app = typer.Typer(name="prompts", help="Manage prompt templates.")
console = Console()

PROMPT_NAMES = ["analyze_trends", "identify_gaps", "synthesize_ideas", "refine_ideas"]


@prompts_app.command("list")
def list_prompts(
    config_path: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Show available prompt templates and override status."""
    from ideagen.cli.config_loader import load_config

    config = load_config(config_path)
    override_dir = config.prompt_override_dir

    table = Table(title="Prompt Templates")
    table.add_column("Name", style="cyan")
    table.add_column("Override", style="green")

    for name in PROMPT_NAMES:
        if override_dir:
            override_path = Path(override_dir) / f"{name}.txt"
            status = "yes" if override_path.exists() else "no"
        else:
            status = "no"
        table.add_row(name, status)

    console.print(table)


@prompts_app.command("init")
def init_prompts(
    directory: Optional[Path] = typer.Option(None, "--dir", help="Directory for prompt templates"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Create prompt template files for customization."""
    from ideagen.cli.config_loader import load_config

    config = load_config(config_path)
    target_dir = directory or (config.prompt_override_dir and Path(config.prompt_override_dir)) or Path("~/.ideagen/prompts").expanduser()
    target_dir = Path(target_dir).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)

    created = 0
    skipped = 0
    for name in PROMPT_NAMES:
        path = target_dir / f"{name}.txt"
        if path.exists():
            skipped += 1
            continue
        path.write_text(f"# Custom prompt template for: {name}\n# Edit this file to override the default prompt.\n")
        created += 1

    console.print(f"[green]Created {created} template(s) in {target_dir}[/green]")
    if skipped:
        console.print(f"[yellow]Skipped {skipped} existing file(s)[/yellow]")
