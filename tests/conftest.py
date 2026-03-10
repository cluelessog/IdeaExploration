"""Shared test fixtures for ideagen."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ideagen.core.models import (
    Domain,
    FeasibilityScore,
    Idea,
    IdeaReport,
    MarketAnalysis,
    MonetizationAngle,
    RunResult,
    TrendingItem,
)
from ideagen.storage.sqlite import SQLiteStorage


# ---------------------------------------------------------------------------
# Factory helpers (importable from any test module)
# ---------------------------------------------------------------------------


def make_idea(title: str = "Test Idea", **overrides) -> Idea:
    defaults = dict(
        title=title,
        problem_statement="A real problem",
        solution="A clever solution",
        domain=Domain.SOFTWARE_SAAS,
        novelty_score=7.5,
        content_hash="abc123",
        tags=["saas", "productivity"],
    )
    defaults.update(overrides)
    return Idea(**defaults)


def make_report(title: str = "Test Idea", wtp_score: float = 4.2, **overrides) -> IdeaReport:
    defaults = dict(
        idea=make_idea(title),
        market_analysis=MarketAnalysis(
            target_audience="Developers",
            market_size_estimate="$1B",
            competitors=["CompA"],
            differentiation="Better UX",
        ),
        feasibility=FeasibilityScore(
            complexity=5,
            time_to_mvp="3 months",
            suggested_tech_stack=["Python", "FastAPI"],
            risks=["Market fit"],
        ),
        monetization=MonetizationAngle(
            revenue_model="SaaS",
            pricing_strategy="Freemium",
            estimated_revenue_potential="$100k ARR",
        ),
        wtp_score=wtp_score,
    )
    defaults.update(overrides)
    return IdeaReport(**defaults)


def make_run(title: str = "Test Idea", timestamp: datetime | None = None, **overrides) -> RunResult:
    defaults = dict(
        ideas=[make_report(title)],
        sources_used=["hackernews", "reddit"],
        domain=Domain.SOFTWARE_SAAS,
        timestamp=timestamp or datetime.now(),
        config_snapshot={"model": "gpt-4o"},
        content_hash="run_hash_001",
        total_items_scraped=42,
        total_after_dedup=30,
    )
    defaults.update(overrides)
    return RunResult(**defaults)


def make_trending_item(title: str = "Trending Post", source: str = "hackernews", **overrides) -> TrendingItem:
    defaults = dict(
        title=title,
        url=f"https://example.com/{title.lower().replace(' ', '-')}",
        score=100,
        source=source,
        timestamp=datetime.now(),
        metadata={},
        comment_count=10,
    )
    defaults.update(overrides)
    return TrendingItem(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_storage(tmp_path: Path) -> SQLiteStorage:
    """SQLiteStorage backed by a temporary database file."""
    db_file = tmp_path / "test.db"
    return SQLiteStorage(db_path=str(db_file))


@pytest.fixture
def runner() -> CliRunner:
    """Shared Typer CLI test runner."""
    return CliRunner()
