"""Natural language 'ask' command for IdeaGen CLI."""

from __future__ import annotations

import typer
from rich.console import Console

ask_app = typer.Typer(name="ask", help="Natural language interface to IdeaGen.")
console = Console()


@ask_app.callback(invoke_without_command=True)
def ask_command(
    query: str = typer.Argument(..., help="Natural language query describing what you want to do"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation for low-confidence interpretations"),
) -> None:
    """Interpret a natural language query and execute the corresponding IdeaGen action."""
    from ideagen.cli.async_bridge import run_async
    from ideagen.core.nl_interpreter import NLInterpreter, NLAction

    interpreter = NLInterpreter()
    action = run_async(interpreter.interpret(query))

    if action is None:
        console.print("[red]Failed to interpret query.[/red]")
        raise typer.Exit(code=1)

    # Show interpretation
    console.print(f"\n[bold cyan]Interpreted:[/bold cyan] {action.explanation}")
    console.print(f"[dim]Command: {action.command} | Confidence: {action.confidence:.0%}[/dim]\n")

    # Ask for confirmation if low confidence
    if action.confidence < 0.7 and not yes:
        confirm = typer.confirm("Confidence is low. Proceed?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit()

    _execute_action(action)


def _execute_action(action: "NLAction") -> None:
    """Execute a parsed NLAction by calling the appropriate library function."""
    command = action.command
    args = action.args

    if command == "run":
        _execute_run(args)
    elif command == "history_list":
        _execute_history_list()
    elif command == "history_show":
        _execute_history_show(args)
    elif command == "history_prune":
        _execute_history_prune(args)
    elif command == "sources_list":
        _execute_sources_list()
    elif command == "sources_test":
        _execute_sources_test()
    elif command == "config_show":
        _execute_config_show()
    elif command == "config_init":
        _execute_config_init()
    elif command == "compare":
        _execute_compare(args)
    else:
        console.print(f"[red]Unknown command: {command}[/red]")
        raise typer.Exit(code=1)


def _execute_run(args: dict) -> None:
    """Execute an idea generation run."""
    from ideagen.cli.async_bridge import run_async
    from ideagen.cli.config_loader import load_config
    from ideagen.cli.formatters import PipelineEventRenderer, format_idea_card, format_run_summary
    from ideagen.sources.registry import get_sources_by_names
    from ideagen.providers.registry import get_provider
    from ideagen.core.service import IdeaGenService
    from ideagen.core.models import CancellationToken, Domain
    from ideagen.storage.sqlite import SQLiteStorage

    config = load_config(None)

    domain_map = {
        "software": Domain.SOFTWARE_SAAS,
        "business": Domain.BROAD_BUSINESS,
        "content": Domain.CONTENT_MEDIA,
    }
    domain_str = args.get("domain", "software")
    domain_enum = domain_map.get(domain_str, Domain.SOFTWARE_SAAS)

    source_names = args.get("source", []) or config.sources.enabled
    if isinstance(source_names, str):
        source_names = [source_names]
    sources = get_sources_by_names(source_names, source_config=config.sources)

    dry_run = args.get("dry_run", False)
    cached = args.get("cached", False)
    segment_ids = args.get("segment", []) or None
    if isinstance(segment_ids, str):
        segment_ids = [segment_ids]
    count = args.get("count", 10)

    if dry_run:
        from ideagen.providers.dry_run import DryRunProvider
        provider = DryRunProvider()
    else:
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
            segment_ids=segment_ids,
            idea_count=count,
        )
        return await renderer.render(events)

    result = run_async(_run(), cancellation_token=token)

    if result and result.ideas:
        console.print()
        console.print(format_run_summary(result))
        console.print()
        for report in result.ideas:
            console.print(format_idea_card(report))
            console.print()
    elif result:
        console.print("[yellow]No ideas generated. Try different domain or segments.[/yellow]")


def _execute_history_list() -> None:
    """List past runs."""
    from ideagen.cli.async_bridge import run_async
    from ideagen.cli.config_loader import load_config
    from ideagen.storage.sqlite import SQLiteStorage
    from rich.table import Table

    config = load_config(None)
    storage = SQLiteStorage(db_path=config.storage.database_path)

    runs = run_async(storage.get_runs(offset=0, limit=20))

    if not runs:
        console.print("[yellow]No runs found.[/yellow]")
        return

    table = Table(title="Past Runs")
    table.add_column("ID", style="dim", max_width=8)
    table.add_column("Timestamp", style="cyan")
    table.add_column("Domain", style="green")
    table.add_column("Ideas", style="yellow")

    for run in runs:
        table.add_row(
            run["id"][:8],
            run["timestamp"][:19],
            run["domain"],
            str(run["ideas_count"]),
        )

    console.print(table)


def _execute_history_show(args: dict) -> None:
    """Show a specific run."""
    from ideagen.cli.async_bridge import run_async
    from ideagen.cli.config_loader import load_config
    from ideagen.cli.formatters import format_idea_card
    from ideagen.storage.sqlite import SQLiteStorage
    from rich.table import Table

    config = load_config(None)
    storage = SQLiteStorage(db_path=config.storage.database_path)

    run_id = args.get("run_id", "latest")

    if run_id == "latest":
        runs = run_async(storage.get_runs(offset=0, limit=1))
        if not runs:
            console.print("[yellow]No runs found.[/yellow]")
            return
        run_id = runs[0]["id"]

    matches = run_async(storage.find_runs_by_prefix(run_id))
    if not matches:
        console.print(f"[red]No run found matching '{run_id}'[/red]")
        raise typer.Exit(code=1)

    detail = run_async(storage.get_run_detail(matches[0]["id"]))
    if detail is None:
        console.print(f"[red]No run found matching '{run_id}'[/red]")
        raise typer.Exit(code=1)

    import json as json_mod
    table = Table(title=f"Run {detail['id'][:8]}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("ID", detail["id"])
    table.add_row("Timestamp", detail["timestamp"][:19])
    table.add_row("Domain", detail["domain"])
    table.add_row("Ideas", str(detail["ideas_count"]))
    console.print(table)

    for report in detail.get("ideas", []):
        console.print(format_idea_card(report))


def _execute_history_prune(args: dict) -> None:
    """Prune old runs."""
    from ideagen.cli.async_bridge import run_async
    from ideagen.cli.config_loader import load_config
    from ideagen.storage.sqlite import SQLiteStorage

    config = load_config(None)
    storage = SQLiteStorage(db_path=config.storage.database_path)

    older_than = args.get("older_than", "30d")
    days = int(older_than.rstrip("d"))

    count = run_async(storage.delete_runs_older_than(days))
    console.print(f"[green]Deleted {count} runs older than {days} days.[/green]")


def _execute_sources_list() -> None:
    """List available sources."""
    from ideagen.cli.config_loader import load_config
    from ideagen.sources.registry import get_available_source_names
    from rich.table import Table

    config = load_config(None)
    enabled = config.sources.enabled
    all_names = get_available_source_names()

    table = Table(title="Data Sources")
    table.add_column("Source", style="cyan")
    table.add_column("Status")

    for name in all_names:
        if name in enabled:
            table.add_row(name, "[green]enabled[/green]")
        else:
            table.add_row(name, "[dim]disabled[/dim]")

    console.print(table)


def _execute_sources_test() -> None:
    """Test source health."""
    from ideagen.cli.async_bridge import run_async
    from ideagen.sources.registry import get_all_sources
    from rich.table import Table

    sources = get_all_sources()
    table = Table(title="Source Health Check")
    table.add_column("Source", style="cyan")
    table.add_column("Status", style="green")

    async def _check():
        for name, source in sources.items():
            try:
                available = await source.is_available()
                status = "[green]OK[/green]" if available else "[red]UNAVAILABLE[/red]"
            except Exception as e:
                status = f"[red]ERROR: {e}[/red]"
            table.add_row(name, status)

    run_async(_check())
    console.print(table)


def _execute_config_show() -> None:
    """Show configuration."""
    from ideagen.cli.config_loader import load_config
    from rich.syntax import Syntax
    import json as json_mod

    config = load_config(None)
    data = config.model_dump(mode="json")

    if data.get("providers", {}).get("openai_api_key"):
        data["providers"]["openai_api_key"] = "***REDACTED***"
    if data.get("providers", {}).get("gemini_api_key"):
        data["providers"]["gemini_api_key"] = "***REDACTED***"

    syntax = Syntax(json_mod.dumps(data, indent=2), "json", theme="monokai")
    console.print(syntax)


def _execute_config_init() -> None:
    """Create default config."""
    from ideagen.cli.config_loader import save_config
    from ideagen.core.config import IdeaGenConfig

    path = save_config(IdeaGenConfig(), None)
    console.print(f"[green]Config created at {path}[/green]")


def _execute_compare(args: dict) -> None:
    """Compare two runs."""
    from ideagen.cli.async_bridge import run_async
    from ideagen.cli.config_loader import load_config
    from ideagen.storage.sqlite import SQLiteStorage
    from ideagen.core.comparison import compare_runs
    from rich.table import Table

    config = load_config(None)
    storage = SQLiteStorage(db_path=config.storage.database_path)

    run1 = args.get("run1", "latest")
    run2 = args.get("run2", "previous")

    # Resolve "latest" and "previous" to actual IDs
    if run1 in ("latest", "previous") or run2 in ("latest", "previous"):
        runs = run_async(storage.get_runs(offset=0, limit=2))
        if len(runs) < 2:
            console.print("[yellow]Need at least 2 runs to compare.[/yellow]")
            return
        if run1 == "latest":
            run1 = runs[0]["id"]
        if run1 == "previous":
            run1 = runs[1]["id"]
        if run2 == "latest":
            run2 = runs[0]["id"]
        if run2 == "previous":
            run2 = runs[1]["id"]

    def resolve_run(prefix: str):
        matches = run_async(storage.find_runs_by_prefix(prefix))
        if not matches:
            console.print(f"[red]No run found matching '{prefix}'[/red]")
            return None
        return run_async(storage.get_run_detail(matches[0]["id"]))

    detail_a = resolve_run(run1)
    detail_b = resolve_run(run2)

    if detail_a is None or detail_b is None:
        raise typer.Exit(code=1)

    result = compare_runs(detail_a, detail_b)

    table = Table(title=f"Comparison: {run1[:8]} vs {run2[:8]}")
    table.add_column("Status", style="bold")
    table.add_column("Idea")
    table.add_column("Detail")

    for title in result.added:
        table.add_row("[green]Added[/green]", title, "New in second run")
    for title in result.removed:
        table.add_row("[red]Removed[/red]", title, "Missing from second run")
    for ta, tb in result.common:
        label = f"{ta}" if ta == tb else f"{ta} -> {tb}"
        table.add_row("[dim]Common[/dim]", label, "")

    console.print(table)

    if not result.added and not result.removed:
        console.print("[green]Runs are identical.[/green]")
