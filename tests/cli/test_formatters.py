"""Tests for ideagen.cli.formatters (PipelineEventRenderer, format_idea_card, format_run_summary)."""
from __future__ import annotations

import asyncio
from io import StringIO

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ideagen.cli.formatters import PipelineEventRenderer, format_idea_card, format_run_summary
from ideagen.core.models import (
    Domain,
    IdeaGenerated,
    IdeaReport,
    MarketAnalysis,
    PipelineComplete,
    RunResult,
    SourceFailed,
    StageCompleted,
    StageStarted,
    WTPSegment,
)
from tests.conftest import _event_stream, make_idea, make_report, make_run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _capture_console() -> tuple[Console, StringIO]:
    """Return a Console that writes to a StringIO buffer (no live markup)."""
    buf = StringIO()
    con = Console(file=buf, force_terminal=True, highlight=False)
    return con, buf


# ---------------------------------------------------------------------------
# format_run_summary
# ---------------------------------------------------------------------------


def test_format_run_summary_returns_table():
    result = make_run()
    table = format_run_summary(result)
    assert isinstance(table, Table)


def test_format_run_summary_contains_all_metrics():
    result = make_run()
    table = format_run_summary(result)

    con, buf = _capture_console()
    con.print(table)
    output = buf.getvalue()

    assert "SOFTWARE_SAAS" in output
    assert "hackernews" in output
    assert "reddit" in output
    assert "42" in output   # total_items_scraped
    assert "30" in output   # total_after_dedup
    assert "1" in output    # ideas generated (len = 1)


# ---------------------------------------------------------------------------
# format_idea_card
# ---------------------------------------------------------------------------


def test_format_idea_card_returns_panel():
    report = make_report()
    panel = format_idea_card(report)
    assert isinstance(panel, Panel)


def test_format_idea_card_contains_all_sections():
    report = make_report(title="My Idea")
    panel = format_idea_card(report)

    con, buf = _capture_console()
    con.print(panel)
    output = buf.getvalue()

    assert "A real problem" in output        # problem_statement
    assert "A clever solution" in output     # solution
    assert "Developers" in output            # target_audience
    assert "Complexity" in output            # feasibility
    assert "SaaS" in output                  # revenue_model
    assert "Freemium" in output              # pricing_strategy
    assert "WTP Score" in output


def test_format_idea_card_empty_competitors():
    report = make_report(
        market_analysis=MarketAnalysis(
            target_audience="Everyone",
            market_size_estimate="$500M",
            competitors=[],
            differentiation="Unique angle",
        )
    )
    panel = format_idea_card(report)

    con, buf = _capture_console()
    con.print(panel)
    output = buf.getvalue()

    assert "None identified" in output


def test_format_idea_card_with_target_segments():
    segment = WTPSegment(
        id="seg1",
        name="Power Users",
        emotional_driver="efficiency",
        spending_areas=["tools"],
        pain_tolerance=4.0,
        wtp_score=4.5,
    )
    report = make_report()
    # Rebuild with target_segments populated
    report = IdeaReport(
        idea=report.idea,
        market_analysis=report.market_analysis,
        feasibility=report.feasibility,
        monetization=report.monetization,
        target_segments=[segment],
        wtp_score=report.wtp_score,
    )
    panel = format_idea_card(report)

    con, buf = _capture_console()
    con.print(panel)
    output = buf.getvalue()

    assert "Power Users" in output


# ---------------------------------------------------------------------------
# PipelineEventRenderer
# ---------------------------------------------------------------------------


def test_renderer_handles_stage_started_and_completed():
    con, buf = _capture_console()
    renderer = PipelineEventRenderer(console=con)

    events = _event_stream(
        StageStarted(stage="collect"),
        StageCompleted(stage="collect", duration_ms=120),
    )
    # Should not raise
    result = asyncio.run(renderer.render(events))
    assert result is None  # no PipelineComplete event


def test_renderer_handles_source_failed():
    con, buf = _capture_console()
    renderer = PipelineEventRenderer(console=con)

    events = _event_stream(
        SourceFailed(source="twitter", error="timeout"),
    )
    asyncio.run(renderer.render(events))
    output = buf.getvalue()

    assert "WARNING" in output
    assert "twitter" in output
    assert "timeout" in output


def test_renderer_handles_idea_generated():
    con, buf = _capture_console()
    renderer = PipelineEventRenderer(console=con)

    idea = make_idea(title="Brilliant Idea")
    events = _event_stream(
        IdeaGenerated(idea=idea, index=0, total=3),
    )
    asyncio.run(renderer.render(events))
    output = buf.getvalue()

    assert "Brilliant Idea" in output


def test_renderer_handles_pipeline_complete():
    con, buf = _capture_console()
    renderer = PipelineEventRenderer(console=con)

    run = make_run()
    events = _event_stream(PipelineComplete(result=run))
    result = asyncio.run(renderer.render(events))

    assert isinstance(result, RunResult)
    assert result is run


def test_renderer_full_pipeline_sequence():
    con, buf = _capture_console()
    renderer = PipelineEventRenderer(console=con)

    idea = make_idea(title="Final Idea")
    run = make_run()
    events = _event_stream(
        StageStarted(stage="collect"),
        StageCompleted(stage="collect", duration_ms=200, metadata={"items": 10}),
        SourceFailed(source="reddit", error="rate limited"),
        StageStarted(stage="analyze"),
        StageCompleted(stage="analyze", duration_ms=500),
        IdeaGenerated(idea=idea, index=0, total=1),
        PipelineComplete(result=run),
    )
    result = asyncio.run(renderer.render(events))

    assert isinstance(result, RunResult)
    output = buf.getvalue()
    assert "WARNING" in output
    assert "Final Idea" in output


def test_renderer_stage_completed_without_stage_started():
    """StageCompleted arriving before any StageStarted must not raise (guards current_task is None)."""
    con, buf = _capture_console()
    renderer = PipelineEventRenderer(console=con)

    events = _event_stream(
        StageCompleted(stage="collect", duration_ms=50),
    )
    # Must not raise despite current_task being None
    result = asyncio.run(renderer.render(events))
    assert result is None


# ---------------------------------------------------------------------------
# DuplicateRunWarning + CacheEmptyWarning renderer tests (Phase 10.1 + 10.2)
# ---------------------------------------------------------------------------

def test_renderer_displays_duplicate_run_warning():
    """Renderer prints a warning when DuplicateRunWarning event arrives."""
    from ideagen.core.models import DuplicateRunWarning

    con, buf = _capture_console()
    renderer = PipelineEventRenderer(console=con)

    events = _event_stream(
        DuplicateRunWarning(existing_run_ids=["abc-123", "def-456"]),
        PipelineComplete(result=make_run()),
    )
    asyncio.run(renderer.render(events))

    output = buf.getvalue()
    assert "WARNING" in output
    assert "Similar run already exists" in output
    assert "abc-123" in output


def test_renderer_displays_cache_empty_warning():
    """Renderer prints a warning when CacheEmptyWarning event arrives."""
    from ideagen.core.models import CacheEmptyWarning

    con, buf = _capture_console()
    renderer = PipelineEventRenderer(console=con)

    events = _event_stream(
        CacheEmptyWarning(),
        PipelineComplete(result=make_run()),
    )
    asyncio.run(renderer.render(events))

    output = buf.getvalue()
    assert "WARNING" in output
    assert "No cached data found" in output
