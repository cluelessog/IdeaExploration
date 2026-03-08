from __future__ import annotations
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from ideagen.core.models import CancellationToken, Domain

run_app = typer.Typer(name="run", help="Run idea generation pipeline.")
console = Console()


@run_app.callback(invoke_without_command=True)
def run_command(
    domain: str = typer.Option("software", "--domain", "-d", help="Domain to explore (software, business, content)"),
    segment: list[str] = typer.Option([], "--segment", "-s", help="Target WTP segment(s)"),
    count: int = typer.Option(10, "--count", "-n", help="Number of ideas to generate"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Export results to file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show pipeline plan without LLM calls"),
    cached: bool = typer.Option(False, "--cached", help="Reuse last scrape data"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Run a single idea generation batch."""
    from ideagen.cli.config_loader import load_config
    from ideagen.cli.async_bridge import run_async
    from ideagen.cli.formatters import PipelineEventRenderer, format_idea_card, format_run_summary
    from ideagen.sources.registry import get_sources_by_names
    from ideagen.providers.registry import get_provider
    from ideagen.core.service import IdeaGenService
    from ideagen.storage.sqlite import SQLiteStorage

    config = load_config(config_path)

    # Map domain string to enum
    domain_map = {"software": Domain.SOFTWARE_SAAS, "business": Domain.BROAD_BUSINESS, "content": Domain.CONTENT_MEDIA}
    domain_enum = domain_map.get(domain, Domain.SOFTWARE_SAAS)

    sources = get_sources_by_names(config.sources.enabled)
    provider = get_provider(config.providers)
    storage = SQLiteStorage(db_path=config.storage.database_path)

    service = IdeaGenService(sources=sources, provider=provider, storage=storage, config=config)
    token = CancellationToken()
    renderer = PipelineEventRenderer(console=console)

    async def _run():
        events = service.run(
            domain=domain_enum,
            dry_run=dry_run,
            cached=cached,
            cancellation_token=token,
            segment_ids=segment if segment else None,
            idea_count=count,
        )
        result = await renderer.render(events)
        return result

    result = run_async(_run(), cancellation_token=token)

    if result and result.ideas:
        console.print()
        console.print(format_run_summary(result))
        console.print()
        for report in result.ideas:
            console.print(format_idea_card(report))
            console.print()

        if output:
            from ideagen.storage.json_export import export_run
            path = export_run(result, output_dir=str(output.parent))
            console.print(f"[green]Results exported to {path}[/green]")
    elif result:
        console.print("[yellow]No ideas generated. Try different domain or segments.[/yellow]")
