"""Tests for ideagen.core.comparison module."""
from __future__ import annotations

import pytest

from ideagen.core.comparison import ComparisonResult, compare_runs, _match_titles
from tests.conftest import make_report


def _make_run_dict(*titles: str, wtp_scores: list[float] | None = None) -> dict:
    """Helper to build a run detail dict with ideas."""
    scores = wtp_scores or [4.0] * len(titles)
    ideas = [make_report(t, wtp_score=s) for t, s in zip(titles, scores)]
    return {"ideas": ideas}


class TestCompareRunsIdentical:
    def test_identical_runs_have_no_added_or_removed(self):
        a = _make_run_dict("Idea A", "Idea B")
        b = _make_run_dict("Idea A", "Idea B")
        result = compare_runs(a, b)
        assert result.added == []
        assert result.removed == []
        assert len(result.common) == 2

    def test_identical_runs_have_no_score_changes(self):
        a = _make_run_dict("Idea A", wtp_scores=[4.0])
        b = _make_run_dict("Idea A", wtp_scores=[4.0])
        result = compare_runs(a, b)
        assert result.score_changes == []


class TestCompareRunsDifferences:
    def test_added_ideas_detected(self):
        a = _make_run_dict("Idea A")
        b = _make_run_dict("Idea A", "Idea B")
        result = compare_runs(a, b)
        assert "Idea B" in result.added
        assert result.removed == []

    def test_removed_ideas_detected(self):
        a = _make_run_dict("Idea A", "Idea B")
        b = _make_run_dict("Idea A")
        result = compare_runs(a, b)
        assert "Idea B" in result.removed
        assert result.added == []

    def test_score_changes_detected(self):
        a = _make_run_dict("Idea A", wtp_scores=[3.0])
        b = _make_run_dict("Idea A", wtp_scores=[4.5])
        result = compare_runs(a, b)
        assert len(result.score_changes) == 1
        assert result.score_changes[0]["score_a"] == 3.0
        assert result.score_changes[0]["score_b"] == 4.5

    def test_small_score_difference_ignored(self):
        a = _make_run_dict("Idea A", wtp_scores=[4.0])
        b = _make_run_dict("Idea A", wtp_scores=[4.05])
        result = compare_runs(a, b)
        assert result.score_changes == []


class TestFuzzyMatching:
    def test_fuzzy_match_pairs_similar_titles(self):
        a = _make_run_dict("AI-Powered Code Review Tool")
        b = _make_run_dict("AI Powered Code Review Tools")
        result = compare_runs(a, b, threshold=0.85)
        assert len(result.common) == 1
        assert result.added == []
        assert result.removed == []

    def test_threshold_controls_sensitivity(self):
        a = _make_run_dict("Code Review")
        b = _make_run_dict("Code Analysis")
        # High threshold should NOT match these
        result_high = compare_runs(a, b, threshold=0.95)
        assert result_high.common == []
        assert len(result_high.added) == 1
        assert len(result_high.removed) == 1

    def test_empty_runs_produce_empty_result(self):
        result = compare_runs({"ideas": []}, {"ideas": []})
        assert result == ComparisonResult(added=[], removed=[], common=[], score_changes=[])


class TestMatchTitles:
    def test_exact_matches(self):
        added, removed, common = _match_titles(["A", "B"], ["A", "B"], 0.85)
        assert added == []
        assert removed == []
        assert len(common) == 2

    def test_no_overlap(self):
        added, removed, common = _match_titles(["X"], ["Y"], 0.99)
        assert added == ["Y"]
        assert removed == ["X"]
        assert common == []
