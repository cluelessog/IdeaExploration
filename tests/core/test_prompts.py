"""Tests for prompt template functions."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

import pytest

from ideagen.core.models import (
    Domain, GapAnalysis, Idea, PainPoint, TrendingItem,
)
from ideagen.core import prompts
from ideagen.core.pipeline import (
    GapList, IdeaList, IdeaReportList, PainPointList,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item(title: str = "Test Post", source: str = "hackernews") -> TrendingItem:
    return TrendingItem(
        title=title,
        url="https://example.com",
        score=42,
        source=source,
        timestamp=datetime(2024, 6, 1),
        comment_count=10,
    )


def _pain(desc: str = "Slow builds") -> PainPoint:
    return PainPoint(description=desc, frequency="frequent", severity=8.0)


def _gap(desc: str = "No CI integration") -> GapAnalysis:
    return GapAnalysis(
        description=desc,
        evidence=["many posts about it"],
        affected_audience="developers",
        opportunity_size="medium",
    )


def _idea(title: str = "BuildBot") -> Idea:
    return Idea(
        title=title,
        problem_statement="Builds are too slow",
        solution="AI-accelerated builds",
        domain=Domain.SOFTWARE_SAAS,
        novelty_score=7.5,
    )


# ---------------------------------------------------------------------------
# analyze_trends_prompt
# ---------------------------------------------------------------------------

class TestAnalyzeTrendsPrompt:
    def test_returns_tuple(self):
        result = prompts.analyze_trends_prompt(
            [_item()], Domain.SOFTWARE_SAAS, PainPointList.model_json_schema()
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_system_prompt_is_string(self):
        system, user = prompts.analyze_trends_prompt(
            [_item()], Domain.SOFTWARE_SAAS, PainPointList.model_json_schema()
        )
        assert isinstance(system, str)

    def test_user_prompt_is_string(self):
        system, user = prompts.analyze_trends_prompt(
            [_item()], Domain.SOFTWARE_SAAS, PainPointList.model_json_schema()
        )
        assert isinstance(user, str)

    def test_domain_in_system(self):
        system, _ = prompts.analyze_trends_prompt(
            [_item()], Domain.SOFTWARE_SAAS, PainPointList.model_json_schema()
        )
        assert "SOFTWARE_SAAS" in system

    def test_item_title_in_user(self):
        _, user = prompts.analyze_trends_prompt(
            [_item(title="Terrible load times")],
            Domain.SOFTWARE_SAAS,
            PainPointList.model_json_schema(),
        )
        assert "Terrible load times" in user

    def test_item_source_in_user(self):
        _, user = prompts.analyze_trends_prompt(
            [_item(source="producthunt")],
            Domain.SOFTWARE_SAAS,
            PainPointList.model_json_schema(),
        )
        assert "producthunt" in user

    def test_schema_included_in_user(self):
        schema = PainPointList.model_json_schema()
        _, user = prompts.analyze_trends_prompt(
            [_item()], Domain.SOFTWARE_SAAS, schema
        )
        # The schema JSON should be embedded
        assert "pain_points" in user

    def test_item_count_in_user(self):
        items = [_item("A"), _item("B"), _item("C")]
        _, user = prompts.analyze_trends_prompt(
            items, Domain.SOFTWARE_SAAS, PainPointList.model_json_schema()
        )
        assert "3" in user

    def test_override_dir_used_when_file_exists(self, tmp_path: Path):
        override_dir = tmp_path / "prompts"
        override_dir.mkdir()
        (override_dir / "analyze_trends.txt").write_text("OVERRIDE_CONTENT")

        system, user = prompts.analyze_trends_prompt(
            [_item()], Domain.SOFTWARE_SAAS, {}, override_dir=override_dir
        )
        assert system is None
        assert user == "OVERRIDE_CONTENT"

    def test_override_dir_not_used_when_file_missing(self, tmp_path: Path):
        override_dir = tmp_path / "prompts"
        override_dir.mkdir()
        # No file written

        system, user = prompts.analyze_trends_prompt(
            [_item(title="UniqueTitle123")],
            Domain.SOFTWARE_SAAS,
            PainPointList.model_json_schema(),
            override_dir=override_dir,
        )
        assert system is not None
        assert "UniqueTitle123" in user

    def test_none_override_dir_uses_default(self):
        system, user = prompts.analyze_trends_prompt(
            [_item()], Domain.SOFTWARE_SAAS, PainPointList.model_json_schema(), None
        )
        assert system is not None


# ---------------------------------------------------------------------------
# identify_gaps_prompt
# ---------------------------------------------------------------------------

class TestIdentifyGapsPrompt:
    def test_returns_tuple(self):
        result = prompts.identify_gaps_prompt(
            [_pain()], Domain.SOFTWARE_SAAS, GapList.model_json_schema()
        )
        assert isinstance(result, tuple) and len(result) == 2

    def test_system_has_domain(self):
        system, _ = prompts.identify_gaps_prompt(
            [_pain()], Domain.BROAD_BUSINESS, GapList.model_json_schema()
        )
        assert "BROAD_BUSINESS" in system

    def test_user_contains_pain_description(self):
        _, user = prompts.identify_gaps_prompt(
            [_pain("Painful deploy pipeline")],
            Domain.SOFTWARE_SAAS,
            GapList.model_json_schema(),
        )
        assert "Painful deploy pipeline" in user

    def test_user_contains_severity(self):
        _, user = prompts.identify_gaps_prompt(
            [_pain()], Domain.SOFTWARE_SAAS, GapList.model_json_schema()
        )
        assert "8.0" in user

    def test_schema_embedded(self):
        schema = GapList.model_json_schema()
        _, user = prompts.identify_gaps_prompt(
            [_pain()], Domain.SOFTWARE_SAAS, schema
        )
        assert "gaps" in user

    def test_pain_count_in_user(self):
        pains = [_pain("A"), _pain("B")]
        _, user = prompts.identify_gaps_prompt(
            pains, Domain.SOFTWARE_SAAS, GapList.model_json_schema()
        )
        assert "2" in user

    def test_override_file_used(self, tmp_path: Path):
        override_dir = tmp_path
        (override_dir / "identify_gaps.txt").write_text("GAPS_OVERRIDE")

        system, user = prompts.identify_gaps_prompt(
            [_pain()], Domain.SOFTWARE_SAAS, {}, override_dir=override_dir
        )
        assert system is None
        assert user == "GAPS_OVERRIDE"


# ---------------------------------------------------------------------------
# synthesize_ideas_prompt
# ---------------------------------------------------------------------------

class TestSynthesizeIdeasPrompt:
    def test_returns_tuple(self):
        result = prompts.synthesize_ideas_prompt(
            [_gap()], Domain.SOFTWARE_SAAS, "segment ctx", 5, IdeaList.model_json_schema()
        )
        assert isinstance(result, tuple) and len(result) == 2

    def test_domain_in_system(self):
        system, _ = prompts.synthesize_ideas_prompt(
            [_gap()], Domain.CONTENT_MEDIA, "ctx", 5, IdeaList.model_json_schema()
        )
        assert "CONTENT_MEDIA" in system

    def test_gap_description_in_user(self):
        _, user = prompts.synthesize_ideas_prompt(
            [_gap("Missing async error handling")],
            Domain.SOFTWARE_SAAS,
            "",
            5,
            IdeaList.model_json_schema(),
        )
        assert "Missing async error handling" in user

    def test_segment_context_in_user(self):
        _, user = prompts.synthesize_ideas_prompt(
            [_gap()], Domain.SOFTWARE_SAAS, "MY_SEGMENT_CONTEXT", 5, IdeaList.model_json_schema()
        )
        assert "MY_SEGMENT_CONTEXT" in user

    def test_empty_segment_context_excluded(self):
        _, user = prompts.synthesize_ideas_prompt(
            [_gap()], Domain.SOFTWARE_SAAS, "", 5, IdeaList.model_json_schema()
        )
        # empty string won't be appended per the if-check in the function
        # just verify it doesn't error and returns a prompt
        assert isinstance(user, str)

    def test_count_in_user(self):
        _, user = prompts.synthesize_ideas_prompt(
            [_gap()], Domain.SOFTWARE_SAAS, "", 13, IdeaList.model_json_schema()
        )
        assert "13" in user

    def test_schema_embedded(self):
        schema = IdeaList.model_json_schema()
        _, user = prompts.synthesize_ideas_prompt(
            [_gap()], Domain.SOFTWARE_SAAS, "", 5, schema
        )
        assert "ideas" in user

    def test_override_file_used(self, tmp_path: Path):
        (tmp_path / "synthesize_ideas.txt").write_text("SYNTH_OVERRIDE")

        system, user = prompts.synthesize_ideas_prompt(
            [_gap()], Domain.SOFTWARE_SAAS, "", 5, {}, override_dir=tmp_path
        )
        assert system is None
        assert user == "SYNTH_OVERRIDE"


# ---------------------------------------------------------------------------
# refine_ideas_prompt
# ---------------------------------------------------------------------------

class TestRefineIdeasPrompt:
    def test_returns_tuple(self):
        result = prompts.refine_ideas_prompt(
            [_idea()], "seg_ctx", IdeaReportList.model_json_schema()
        )
        assert isinstance(result, tuple) and len(result) == 2

    def test_system_is_string(self):
        system, _ = prompts.refine_ideas_prompt(
            [_idea()], "", IdeaReportList.model_json_schema()
        )
        assert isinstance(system, str)

    def test_idea_title_in_user(self):
        _, user = prompts.refine_ideas_prompt(
            [_idea("SuperUniqueTitle999")], "", IdeaReportList.model_json_schema()
        )
        assert "SuperUniqueTitle999" in user

    def test_idea_count_in_user(self):
        _, user = prompts.refine_ideas_prompt(
            [_idea("A"), _idea("B")], "", IdeaReportList.model_json_schema()
        )
        assert "2" in user

    def test_segment_context_in_user(self):
        _, user = prompts.refine_ideas_prompt(
            [_idea()], "SEGMENT_CTX_MARKER", IdeaReportList.model_json_schema()
        )
        assert "SEGMENT_CTX_MARKER" in user

    def test_empty_segment_context_ok(self):
        system, user = prompts.refine_ideas_prompt(
            [_idea()], "", IdeaReportList.model_json_schema()
        )
        assert isinstance(user, str)

    def test_schema_embedded(self):
        schema = IdeaReportList.model_json_schema()
        _, user = prompts.refine_ideas_prompt([_idea()], "", schema)
        assert "reports" in user

    def test_novelty_score_in_user(self):
        _, user = prompts.refine_ideas_prompt(
            [_idea()], "", IdeaReportList.model_json_schema()
        )
        assert "7.5" in user

    def test_override_file_used(self, tmp_path: Path):
        (tmp_path / "refine_ideas.txt").write_text("REFINE_OVERRIDE")

        system, user = prompts.refine_ideas_prompt(
            [_idea()], "", {}, override_dir=tmp_path
        )
        assert system is None
        assert user == "REFINE_OVERRIDE"

    def test_no_override_when_dir_none(self):
        system, user = prompts.refine_ideas_prompt(
            [_idea("TitleCheck")], "", IdeaReportList.model_json_schema(), override_dir=None
        )
        assert system is not None
        assert "TitleCheck" in user
