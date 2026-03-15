from __future__ import annotations
import asyncio
import os
import sys
from collections.abc import AsyncIterator
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from ideagen.core.models import (
    PipelineEvent, StageStarted, StageCompleted, SourceFailed,
    IdeaGenerated, PipelineComplete, IdeaReport, RunResult,
    DuplicateRunWarning, CacheEmptyWarning,
)

console = Console()


def _get_spinner_column() -> SpinnerColumn:
    """Return an ASCII-safe SpinnerColumn on non-UTF-8 terminals, default otherwise."""
    encoding = getattr(sys.stdout, "encoding", None) or ""
    if encoding.lower().startswith("cp") or encoding.lower() == "ascii":
        return SpinnerColumn(spinner_name="line")
    return SpinnerColumn()


class PipelineEventRenderer:
    """Consumes AsyncIterator[PipelineEvent] and renders Rich progress."""

    def __init__(self, console: Console | None = None):
        self._console = console or Console()

    async def render(self, events: AsyncIterator[PipelineEvent]) -> RunResult | None:
        """Consume events, display progress, return final RunResult."""
        result = None

        with Progress(
            _get_spinner_column(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=self._console,
        ) as progress:
            current_task = None

            async for event in events:
                if isinstance(event, StageStarted):
                    desc = f"[cyan]{event.stage}[/cyan]..."
                    current_task = progress.add_task(desc, total=None)

                elif isinstance(event, StageCompleted):
                    if current_task is not None:
                        meta = event.metadata
                        detail = ", ".join(f"{k}={v}" for k, v in meta.items())
                        progress.update(
                            current_task,
                            description=f"[green]{event.stage}[/green] ({event.duration_ms}ms{', ' + detail if detail else ''})",
                            completed=True,
                        )

                elif isinstance(event, SourceFailed):
                    self._console.print(f"  [yellow]WARNING[/yellow] Source '{event.source}' failed: {event.error}")

                elif isinstance(event, IdeaGenerated):
                    self._console.print(f"  [blue]Idea {event.index + 1}/{event.total}:[/blue] {event.idea.title}")

                elif isinstance(event, DuplicateRunWarning):
                    ids = ", ".join(event.existing_run_ids[:3])
                    self._console.print(f"  [yellow]WARNING[/yellow] Similar run already exists (run IDs: {ids})")

                elif isinstance(event, CacheEmptyWarning):
                    self._console.print("  [yellow]WARNING[/yellow] No cached data found. Run without --cached first.")

                elif isinstance(event, PipelineComplete):
                    result = event.result

        return result


def format_idea_card(report: IdeaReport) -> Panel:
    """Format a single idea report as a Rich panel."""
    content = (
        f"[bold]{report.idea.title}[/bold]\n\n"
        f"[cyan]Problem:[/cyan] {report.idea.problem_statement}\n"
        f"[green]Solution:[/green] {report.idea.solution}\n\n"
        f"[yellow]Market:[/yellow] {report.market_analysis.target_audience} "
        f"({report.market_analysis.market_size_estimate})\n"
        f"[yellow]Competitors:[/yellow] {', '.join(report.market_analysis.competitors) or 'None identified'}\n"
        f"[yellow]Differentiation:[/yellow] {report.market_analysis.differentiation}\n\n"
        f"[magenta]Feasibility:[/magenta] Complexity {report.feasibility.complexity}/10, "
        f"MVP in {report.feasibility.time_to_mvp}\n"
        f"[magenta]Tech Stack:[/magenta] {', '.join(report.feasibility.suggested_tech_stack) or 'TBD'}\n"
        f"[magenta]Risks:[/magenta] {', '.join(report.feasibility.risks) or 'None identified'}\n\n"
        f"[red]Revenue:[/red] {report.monetization.revenue_model} — {report.monetization.pricing_strategy}\n"
        f"[red]Potential:[/red] {report.monetization.estimated_revenue_potential}\n\n"
        f"WTP Score: {report.wtp_score:.1f}/5.0 | Novelty: {report.idea.novelty_score:.1f}/10"
    )

    segments = ", ".join(s.name for s in report.target_segments)
    subtitle = f"Segments: {segments}" if segments else None

    return Panel(content, title=report.idea.title, subtitle=subtitle, border_style="blue")


def format_run_as_markdown(result: RunResult) -> str:
    """Format a RunResult as a markdown string."""
    lines: list[str] = []
    lines.append("# IdeaGen Run Report")
    lines.append(f"**Date:** {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Domain:** {result.domain.value}")
    lines.append(f"**Sources:** {', '.join(result.sources_used)}")
    lines.append("")
    lines.append("## Ideas")
    lines.append("")
    for i, report in enumerate(result.ideas, start=1):
        lines.append(f"### {i}. {report.idea.title}")
        lines.append(f"**Problem:** {report.idea.problem_statement}")
        lines.append(f"**Solution:** {report.idea.solution}")
        lines.append(f"**WTP Score:** {report.wtp_score:.1f}/5.0")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def format_run_summary(result: RunResult) -> Table:
    """Format a run result as a summary table."""
    table = Table(title="IdeaGen Run Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Domain", result.domain.value)
    table.add_row("Sources", ", ".join(result.sources_used))
    table.add_row("Items Scraped", str(result.total_items_scraped))
    table.add_row("After Dedup", str(result.total_after_dedup))
    table.add_row("Ideas Generated", str(len(result.ideas)))
    table.add_row("Timestamp", result.timestamp.strftime("%Y-%m-%d %H:%M:%S"))

    return table
