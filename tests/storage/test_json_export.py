from __future__ import annotations

import json
from pathlib import Path

import pytest

from ideagen.core.models import (
    Domain,
    Idea,
    IdeaReport,
    MarketAnalysis,
    FeasibilityScore,
    MonetizationAngle,
    RunResult,
)
from ideagen.storage.json_export import export_idea, export_run


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_idea(title: str = "Test Idea") -> Idea:
    return Idea(
        title=title,
        problem_statement="A real problem",
        solution="A clever solution",
        domain=Domain.SOFTWARE_SAAS,
        novelty_score=8.0,
        content_hash="hash001",
    )


def _make_report(title: str = "Test Idea") -> IdeaReport:
    return IdeaReport(
        idea=_make_idea(title),
        market_analysis=MarketAnalysis(
            target_audience="Developers",
            market_size_estimate="$500M",
            competitors=["Rival A"],
            differentiation="Faster",
        ),
        feasibility=FeasibilityScore(
            complexity=4,
            time_to_mvp="2 months",
            suggested_tech_stack=["Python"],
            risks=["Competition"],
        ),
        monetization=MonetizationAngle(
            revenue_model="Subscription",
            pricing_strategy="Tiered",
            estimated_revenue_potential="$50k ARR",
        ),
        wtp_score=3.9,
    )


def _make_run(title: str = "Test Idea") -> RunResult:
    return RunResult(
        ideas=[_make_report(title)],
        sources_used=["hackernews"],
        domain=Domain.SOFTWARE_SAAS,
        config_snapshot={"model": "gpt-4o"},
        content_hash="run_hash",
        total_items_scraped=10,
        total_after_dedup=8,
    )


# ---------------------------------------------------------------------------
# export_run tests
# ---------------------------------------------------------------------------

def test_export_run_creates_file(tmp_path: Path) -> None:
    """export_run creates a JSON file in the output directory."""
    run = _make_run()
    file_path = export_run(run, output_dir=str(tmp_path))
    assert file_path.exists()
    assert file_path.suffix == ".json"


def test_export_run_filename_contains_timestamp(tmp_path: Path) -> None:
    """export_run filename starts with ideagen_run_ and includes a timestamp."""
    run = _make_run()
    file_path = export_run(run, output_dir=str(tmp_path))
    assert file_path.name.startswith("ideagen_run_")


def test_export_run_valid_json(tmp_path: Path) -> None:
    """export_run writes valid JSON that can be parsed."""
    run = _make_run()
    file_path = export_run(run, output_dir=str(tmp_path))
    content = file_path.read_text()
    data = json.loads(content)
    assert isinstance(data, dict)


def test_export_run_contains_all_fields(tmp_path: Path) -> None:
    """export_run includes all RunResult fields in the output."""
    run = _make_run("My Run Idea")
    file_path = export_run(run, output_dir=str(tmp_path))
    data = json.loads(file_path.read_text())

    assert "ideas" in data
    assert "sources_used" in data
    assert "domain" in data
    assert "timestamp" in data
    assert "config_snapshot" in data
    assert "total_items_scraped" in data
    assert "total_after_dedup" in data

    assert data["domain"] == Domain.SOFTWARE_SAAS.value
    assert data["total_items_scraped"] == 10
    assert len(data["ideas"]) == 1
    assert data["ideas"][0]["idea"]["title"] == "My Run Idea"


def test_export_run_is_indented(tmp_path: Path) -> None:
    """export_run produces human-readable (indented) JSON."""
    run = _make_run()
    file_path = export_run(run, output_dir=str(tmp_path))
    content = file_path.read_text()
    # Indented JSON has newlines
    assert "\n" in content
    # At least one line starts with spaces (indented)
    lines = content.splitlines()
    assert any(line.startswith("  ") for line in lines)


def test_export_run_creates_output_dir_if_missing(tmp_path: Path) -> None:
    """export_run creates the output directory if it does not exist."""
    new_dir = tmp_path / "nested" / "output"
    assert not new_dir.exists()
    run = _make_run()
    file_path = export_run(run, output_dir=str(new_dir))
    assert new_dir.exists()
    assert file_path.exists()


# ---------------------------------------------------------------------------
# export_idea tests
# ---------------------------------------------------------------------------

def test_export_idea_creates_file(tmp_path: Path) -> None:
    """export_idea creates a JSON file in the output directory."""
    report = _make_report("Simple Idea")
    file_path = export_idea(report, output_dir=str(tmp_path))
    assert file_path.exists()
    assert file_path.suffix == ".json"


def test_export_idea_sanitized_title_in_filename(tmp_path: Path) -> None:
    """export_idea uses a sanitized version of the idea title in the filename."""
    report = _make_report("Hello World Idea!")
    file_path = export_idea(report, output_dir=str(tmp_path))
    # Spaces replaced with underscores, special chars stripped
    assert "Hello_World_Idea" in file_path.name
    assert "!" not in file_path.name


def test_export_idea_valid_json(tmp_path: Path) -> None:
    """export_idea writes valid JSON."""
    report = _make_report()
    file_path = export_idea(report, output_dir=str(tmp_path))
    data = json.loads(file_path.read_text())
    assert isinstance(data, dict)


def test_export_idea_contains_all_fields(tmp_path: Path) -> None:
    """export_idea includes all IdeaReport fields."""
    report = _make_report("Field Check Idea")
    file_path = export_idea(report, output_dir=str(tmp_path))
    data = json.loads(file_path.read_text())

    assert "idea" in data
    assert "market_analysis" in data
    assert "feasibility" in data
    assert "monetization" in data
    assert "wtp_score" in data
    assert "generated_at" in data

    assert data["idea"]["title"] == "Field Check Idea"
    assert data["wtp_score"] == pytest.approx(3.9)


def test_export_idea_is_indented(tmp_path: Path) -> None:
    """export_idea produces human-readable (indented) JSON."""
    report = _make_report()
    file_path = export_idea(report, output_dir=str(tmp_path))
    content = file_path.read_text()
    assert "\n" in content
    lines = content.splitlines()
    assert any(line.startswith("  ") for line in lines)


def test_export_idea_creates_output_dir_if_missing(tmp_path: Path) -> None:
    """export_idea creates the output directory if it does not exist."""
    new_dir = tmp_path / "ideas_out"
    assert not new_dir.exists()
    report = _make_report()
    file_path = export_idea(report, output_dir=str(new_dir))
    assert new_dir.exists()
    assert file_path.exists()


def test_export_idea_long_title_truncated(tmp_path: Path) -> None:
    """export_idea truncates very long titles to 50 chars in the filename."""
    long_title = "A" * 100
    report = _make_report(long_title)
    file_path = export_idea(report, output_dir=str(tmp_path))
    # idea_ prefix + max 50 chars of title + .json
    name_without_prefix = file_path.stem[len("idea_"):]
    assert len(name_without_prefix) <= 50
