"""Tests for ideagen.core.dedup."""
from __future__ import annotations
from datetime import datetime

import pytest

from ideagen.core.dedup import (
    content_hash,
    deduplicate,
    idea_content_hash,
    run_content_hash,
)
from ideagen.core.models import (
    Domain,
    Idea,
    IdeaReport,
    FeasibilityScore,
    MarketAnalysis,
    MonetizationAngle,
    RunResult,
    TrendingItem,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item(title: str, score: int = 100, source: str = "hackernews") -> TrendingItem:
    return TrendingItem(
        title=title,
        url="https://example.com",
        score=score,
        source=source,
        timestamp=datetime(2024, 1, 1),
    )


def _idea(title: str = "App") -> Idea:
    return Idea(
        title=title,
        problem_statement="A problem",
        solution="A solution",
        domain=Domain.SOFTWARE_SAAS,
        novelty_score=7.0,
    )


def _report(title: str = "App") -> IdeaReport:
    return IdeaReport(
        idea=_idea(title),
        market_analysis=MarketAnalysis(
            target_audience="devs",
            market_size_estimate="$1B",
            competitors=[],
            differentiation="fast",
        ),
        feasibility=FeasibilityScore(
            complexity=4,
            time_to_mvp="2 months",
            suggested_tech_stack=["Python"],
            risks=[],
        ),
        monetization=MonetizationAngle(
            revenue_model="SaaS",
            pricing_strategy="$19/mo",
            estimated_revenue_potential="$100k ARR",
        ),
    )


def _run_result(titles: list[str]) -> RunResult:
    return RunResult(
        ideas=[_report(t) for t in titles],
        sources_used=["hackernews"],
        domain=Domain.SOFTWARE_SAAS,
    )


# ---------------------------------------------------------------------------
# deduplicate()
# ---------------------------------------------------------------------------

class TestDeduplicate:
    def test_empty_list_returns_empty(self):
        assert deduplicate([]) == []

    def test_single_item_returned_unchanged(self):
        item = _item("Deploy automation tool")
        result = deduplicate([item])
        assert result == [item]

    def test_distinct_items_all_kept(self):
        items = [
            _item("Deploy automation tool"),
            _item("Database migration helper"),
            _item("CI/CD pipeline builder"),
        ]
        result = deduplicate(items)
        assert len(result) == 3

    def test_near_identical_titles_deduplicated(self):
        # These titles are nearly identical and should collapse to one
        items = [
            _item("Deploy automation tool", score=50),
            _item("Deploy automation tools", score=80),
        ]
        result = deduplicate(items)
        assert len(result) == 1

    def test_keeps_higher_score_on_dedup(self):
        low = _item("Deploy automation tool", score=10)
        high = _item("Deploy automation tools", score=99)
        # low first, then high — high should win
        result = deduplicate([low, high])
        assert len(result) == 1
        assert result[0].score == 99

    def test_keeps_original_when_duplicate_has_lower_score(self):
        high = _item("Deploy automation tool", score=99)
        low = _item("Deploy automation tools", score=10)
        # high first, then low — high should be kept
        result = deduplicate([high, low])
        assert len(result) == 1
        assert result[0].score == 99

    def test_case_insensitive_comparison(self):
        items = [
            _item("DEPLOY AUTOMATION TOOL", score=50),
            _item("deploy automation tool", score=60),
        ]
        result = deduplicate(items)
        assert len(result) == 1
        assert result[0].score == 60

    def test_threshold_default_85(self):
        # At default 0.85, slightly different titles should not be deduped
        items = [
            _item("Fast database backup"),
            _item("Slow database restore"),
        ]
        result = deduplicate(items, threshold=0.85)
        assert len(result) == 2

    def test_lower_threshold_more_aggressive(self):
        # Lower threshold collapses more items
        items = [
            _item("Fast database backup"),
            _item("Fast database backups"),
        ]
        # Default 0.85 — these are very similar, should collapse
        result_default = deduplicate(items, threshold=0.85)
        assert len(result_default) == 1

        # Very high threshold — exact match only, these may pass through
        result_strict = deduplicate(items, threshold=0.99)
        assert len(result_strict) == 2

    def test_multiple_duplicates_all_collapse(self):
        items = [
            _item("Deploy automation tool", score=10),
            _item("Deploy automation tools", score=20),
            _item("Deploy automation tools!", score=5),
        ]
        result = deduplicate(items)
        assert len(result) == 1
        assert result[0].score == 20

    def test_preserves_non_duplicate_order(self):
        items = [
            _item("Alpha tool"),
            _item("Beta tool"),
            _item("Gamma tool"),
        ]
        result = deduplicate(items)
        titles = [r.title for r in result]
        assert titles == ["Alpha tool", "Beta tool", "Gamma tool"]


# ---------------------------------------------------------------------------
# content_hash()
# ---------------------------------------------------------------------------

class TestContentHash:
    def test_same_input_same_hash(self):
        assert content_hash("hello world") == content_hash("hello world")

    def test_different_input_different_hash(self):
        assert content_hash("hello world") != content_hash("goodbye world")

    def test_returns_16_char_hex_string(self):
        h = content_hash("test")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_empty_string_is_stable(self):
        h1 = content_hash("")
        h2 = content_hash("")
        assert h1 == h2

    def test_case_sensitive(self):
        assert content_hash("Hello") != content_hash("hello")


# ---------------------------------------------------------------------------
# idea_content_hash()
# ---------------------------------------------------------------------------

class TestIdeaContentHash:
    def test_deterministic(self):
        h1 = idea_content_hash("Title", "Problem", "Solution")
        h2 = idea_content_hash("Title", "Problem", "Solution")
        assert h1 == h2

    def test_different_title_different_hash(self):
        h1 = idea_content_hash("Title A", "Problem", "Solution")
        h2 = idea_content_hash("Title B", "Problem", "Solution")
        assert h1 != h2

    def test_different_problem_different_hash(self):
        h1 = idea_content_hash("Title", "Problem A", "Solution")
        h2 = idea_content_hash("Title", "Problem B", "Solution")
        assert h1 != h2

    def test_different_solution_different_hash(self):
        h1 = idea_content_hash("Title", "Problem", "Solution A")
        h2 = idea_content_hash("Title", "Problem", "Solution B")
        assert h1 != h2

    def test_returns_16_char_string(self):
        h = idea_content_hash("T", "P", "S")
        assert len(h) == 16


# ---------------------------------------------------------------------------
# run_content_hash()
# ---------------------------------------------------------------------------

class TestRunContentHash:
    def test_deterministic(self):
        result = _run_result(["AppA", "AppB"])
        h1 = run_content_hash(result)
        h2 = run_content_hash(result)
        assert h1 == h2

    def test_order_independent(self):
        # Titles are sorted internally so order of ideas doesn't matter
        r1 = _run_result(["AppA", "AppB"])
        r2 = _run_result(["AppB", "AppA"])
        assert run_content_hash(r1) == run_content_hash(r2)

    def test_different_ideas_different_hash(self):
        r1 = _run_result(["AppA", "AppB"])
        r2 = _run_result(["AppA", "AppC"])
        assert run_content_hash(r1) != run_content_hash(r2)

    def test_empty_run_is_stable(self):
        r = _run_result([])
        h1 = run_content_hash(r)
        h2 = run_content_hash(r)
        assert h1 == h2

    def test_returns_16_char_string(self):
        r = _run_result(["AppA"])
        assert len(run_content_hash(r)) == 16
