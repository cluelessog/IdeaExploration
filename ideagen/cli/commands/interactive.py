from __future__ import annotations
import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

interactive_app = typer.Typer(name="interactive", help="Interactive idea exploration.")
console = Console()


@interactive_app.callback(invoke_without_command=True)
def interactive_mode(
    domain: str = typer.Option("software", "--domain", "-d"),
    config_path: str = typer.Option(None, "--config", "-c"),
) -> None:
    """Start interactive idea generation REPL."""
    from ideagen.cli.config_loader import load_config
    from ideagen.cli.async_bridge import run_async
    from ideagen.cli.formatters import PipelineEventRenderer, format_idea_card, format_run_summary
    from ideagen.sources.registry import get_sources_by_names
    from ideagen.providers.registry import get_provider
    from ideagen.core.service import IdeaGenService
    from ideagen.core.models import CancellationToken, Domain
    from pathlib import Path

    config = load_config(Path(config_path) if config_path else None)
    domain_map = {"software": Domain.SOFTWARE_SAAS, "business": Domain.BROAD_BUSINESS, "content": Domain.CONTENT_MEDIA}
    domain_enum = domain_map.get(domain, Domain.SOFTWARE_SAAS)

    sources = get_sources_by_names(config.sources.enabled)
    provider = get_provider(config.providers)
    service = IdeaGenService(sources=sources, provider=provider, config=config)

    console.print("[bold cyan]IdeaGen Interactive Mode[/bold cyan]")
    console.print("Commands: [green]generate[/green], [green]list[/green], [green]detail <n>[/green], [green]export[/green], [green]quit[/green]\n")

    current_result = None

    while True:
        try:
            cmd = Prompt.ask("[bold]ideagen[/bold]", default="help")
        except (EOFError, KeyboardInterrupt):
            break

        parts = cmd.strip().split()
        if not parts:
            continue

        action = parts[0].lower()

        if action in ("quit", "exit", "q"):
            break

        elif action in ("generate", "new", "run"):
            token = CancellationToken()
            renderer = PipelineEventRenderer(console=console)

            async def _run():
                events = service.run(domain=domain_enum, cancellation_token=token)
                return await renderer.render(events)

            current_result = run_async(_run(), cancellation_token=token)
            if current_result and current_result.ideas:
                console.print(format_run_summary(current_result))

        elif action == "list":
            if not current_result or not current_result.ideas:
                console.print("[yellow]No ideas yet. Run 'generate' first.[/yellow]")
                continue
            table = Table(title="Generated Ideas")
            table.add_column("#", style="dim")
            table.add_column("Title", style="cyan")
            table.add_column("WTP", style="green")
            table.add_column("Novelty", style="yellow")
            for i, r in enumerate(current_result.ideas):
                table.add_row(str(i + 1), r.idea.title, f"{r.wtp_score:.1f}", f"{r.idea.novelty_score:.1f}")
            console.print(table)

        elif action == "detail":
            if not current_result or not current_result.ideas:
                console.print("[yellow]No ideas yet.[/yellow]")
                continue
            try:
                idx = int(parts[1]) - 1
                report = current_result.ideas[idx]
                console.print(format_idea_card(report))
            except (IndexError, ValueError):
                console.print("[red]Usage: detail <number>[/red]")

        elif action == "export":
            if not current_result:
                console.print("[yellow]No results to export.[/yellow]")
                continue
            from ideagen.storage.json_export import export_run
            path = export_run(current_result)
            console.print(f"[green]Exported to {path}[/green]")

        else:
            # Try NL interpretation for unrecognized commands
            _try_nl_interpret(cmd, console)

    console.print("[dim]Goodbye![/dim]")


def _try_nl_interpret(user_input: str, console: Console) -> None:
    """Attempt to interpret unrecognized input as natural language via NLInterpreter."""
    from ideagen.cli.async_bridge import run_async
    from ideagen.core.nl_interpreter import NLInterpreter
    from ideagen.core.exceptions import ProviderError

    try:
        interpreter = NLInterpreter()
        action = run_async(interpreter.interpret(user_input))
    except ProviderError:
        console.print(
            "Commands: [green]generate[/green], [green]list[/green], "
            "[green]detail <n>[/green], [green]export[/green], [green]quit[/green]\n"
            "[dim]Tip: Install Claude CLI for natural language support.[/dim]"
        )
        return

    if action is None:
        console.print("Commands: [green]generate[/green], [green]list[/green], [green]detail <n>[/green], [green]export[/green], [green]quit[/green]")
        return

    console.print(f"\n[bold cyan]Interpreted:[/bold cyan] {action.explanation}")
    console.print(f"[dim]Command: {action.command} | Confidence: {action.confidence:.0%}[/dim]")

    if action.confidence < 0.7:
        from rich.prompt import Confirm
        if not Confirm.ask("Confidence is low. Proceed?", default=False):
            console.print("[yellow]Cancelled.[/yellow]")
            return

    from ideagen.cli.commands.ask import _execute_action
    _execute_action(action)
