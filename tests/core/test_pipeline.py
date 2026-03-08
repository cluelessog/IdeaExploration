"""Tests for AnalysisPipeline."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import TypeVar
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from ideagen.core.models import (
    Domain, GapAnalysis, Idea, IdeaReport, MarketAnalysis,
    FeasibilityScore, MonetizationAngle, PainPoint, TrendingItem, WTPSegment,
)
from ideagen.core.pipeline import (
    AnalysisPipeline, GapList, IdeaList, IdeaReportList, PainPointList,
)
from ideagen.providers.base import AIProvider

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _trending_item(title: str = "Test Item", source: str = "hackernews") -> TrendingItem:
    return TrendingItem(
        title=title,
        url="https://example.com",
        score=100,
        source=source,
        timestamp=datetime(2024, 1, 1),
        comment_count=50,
    )


def _pain_point(desc: str = "Too slow") -> PainPoint:
    return PainPoint(description=desc, frequency="frequent", severity=7.0)


def _gap(desc: str = "No fast solution") -> GapAnalysis:
    return GapAnalysis(
        description=desc,
        evidence=["evidence 1"],
        affected_audience="developers",
        opportunity_size="large",
    )


def _idea(title: str = "SpeedApp") -> Idea:
    return Idea(
        title=title,
        problem_statement="It's too slow",
        solution="Make it fast",
        domain=Domain.SOFTWARE_SAAS,
        novelty_score=8.0,
    )


def _idea_report(idea: Idea | None = None) -> IdeaReport:
    return IdeaReport(
        idea=idea or _idea(),
        market_analysis=MarketAnalysis(
            target_audience="devs",
            market_size_estimate="$1B",
            competitors=["CompA"],
            differentiation="faster",
        ),
        feasibility=FeasibilityScore(
            complexity=5,
            time_to_mvp="3 months",
            suggested_tech_stack=["Python"],
            risks=["low adoption"],
        ),
        monetization=MonetizationAngle(
            revenue_model="SaaS",
            pricing_strategy="$29/mo",
            estimated_revenue_potential="$500k ARR",
        ),
        target_segments=[],
        wtp_score=3.5,
    )


class MockProvider(AIProvider):
    """Configurable mock that returns pre-built Pydantic models."""

    def __init__(self):
        self._responses: list[BaseModel] = []
        self.calls: list[dict] = []

    def queue(self, response: BaseModel) -> "MockProvider":
        self._responses.append(response)
        return self

    async def complete(
        self,
        user_prompt: str,
        response_type: type[T],
        system_prompt: str | None = None,
    ) -> T:
        self.calls.append({
            "user_prompt": user_prompt,
            "response_type": response_type,
            "system_prompt": system_prompt,
        })
        if not self._responses:
            raise RuntimeError("MockProvider has no queued responses")
        return self._responses.pop(0)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# analyze()
# ---------------------------------------------------------------------------

class TestAnalyze:
    @pytest.mark.asyncio
    async def test_returns_pain_points(self):
        pain = _pain_point()
        provider = MockProvider()
        provider.queue(PainPointList(pain_points=[pain]))
        pipeline = AnalysisPipeline(provider)

        result = await pipeline.analyze([_trending_item()], Domain.SOFTWARE_SAAS)

        assert len(result) == 1
        assert result[0].description == "Too slow"

    @pytest.mark.asyncio
    async def test_passes_domain_to_prompt(self):
        provider = MockProvider()
        provider.queue(PainPointList(pain_points=[]))
        pipeline = AnalysisPipeline(provider)

        await pipeline.analyze([_trending_item()], Domain.BROAD_BUSINESS)

        call = provider.calls[0]
        assert "BROAD_BUSINESS" in call["system_prompt"]

    @pytest.mark.asyncio
    async def test_items_appear_in_prompt(self):
        provider = MockProvider()
        provider.queue(PainPointList(pain_points=[]))
        pipeline = AnalysisPipeline(provider)

        await pipeline.analyze(
            [_trending_item(title="Slow deploy times", source="reddit")],
            Domain.SOFTWARE_SAAS,
        )

        call = provider.calls[0]
        assert "Slow deploy times" in call["user_prompt"]
        assert "reddit" in call["user_prompt"]

    @pytest.mark.asyncio
    async def test_empty_items_list(self):
        provider = MockProvider()
        provider.queue(PainPointList(pain_points=[]))
        pipeline = AnalysisPipeline(provider)

        result = await pipeline.analyze([], Domain.SOFTWARE_SAAS)
        assert result == []

    @pytest.mark.asyncio
    async def test_uses_painpointlist_response_type(self):
        provider = MockProvider()
        provider.queue(PainPointList(pain_points=[]))
        pipeline = AnalysisPipeline(provider)

        await pipeline.analyze([_trending_item()], Domain.SOFTWARE_SAAS)

        assert provider.calls[0]["response_type"] is PainPointList


# ---------------------------------------------------------------------------
# identify_gaps()
# ---------------------------------------------------------------------------

class TestIdentifyGaps:
    @pytest.mark.asyncio
    async def test_returns_gap_list(self):
        gap = _gap()
        provider = MockProvider()
        provider.queue(GapList(gaps=[gap]))
        pipeline = AnalysisPipeline(provider)

        result = await pipeline.identify_gaps([_pain_point()], Domain.SOFTWARE_SAAS)

        assert len(result) == 1
        assert result[0].description == "No fast solution"

    @pytest.mark.asyncio
    async def test_pain_points_appear_in_prompt(self):
        provider = MockProvider()
        provider.queue(GapList(gaps=[]))
        pipeline = AnalysisPipeline(provider)

        await pipeline.identify_gaps(
            [_pain_point("Terrible onboarding UX")],
            Domain.SOFTWARE_SAAS,
        )

        call = provider.calls[0]
        assert "Terrible onboarding UX" in call["user_prompt"]

    @pytest.mark.asyncio
    async def test_domain_in_system_prompt(self):
        provider = MockProvider()
        provider.queue(GapList(gaps=[]))
        pipeline = AnalysisPipeline(provider)

        await pipeline.identify_gaps([_pain_point()], Domain.CONTENT_MEDIA)

        assert "CONTENT_MEDIA" in provider.calls[0]["system_prompt"]

    @pytest.mark.asyncio
    async def test_uses_gaplist_response_type(self):
        provider = MockProvider()
        provider.queue(GapList(gaps=[]))
        pipeline = AnalysisPipeline(provider)

        await pipeline.identify_gaps([_pain_point()], Domain.SOFTWARE_SAAS)

        assert provider.calls[0]["response_type"] is GapList


# ---------------------------------------------------------------------------
# synthesize()
# ---------------------------------------------------------------------------

class TestSynthesize:
    @pytest.mark.asyncio
    async def test_returns_ideas(self):
        idea = _idea()
        provider = MockProvider()
        provider.queue(IdeaList(ideas=[idea]))
        pipeline = AnalysisPipeline(provider)

        result = await pipeline.synthesize([_gap()], Domain.SOFTWARE_SAAS)

        assert len(result) == 1
        assert result[0].title == "SpeedApp"

    @pytest.mark.asyncio
    async def test_includes_wtp_segment_context(self):
        provider = MockProvider()
        provider.queue(IdeaList(ideas=[]))
        pipeline = AnalysisPipeline(provider)

        await pipeline.synthesize([_gap()], Domain.SOFTWARE_SAAS)

        call = provider.calls[0]
        # format_segments_for_prompt adds a heading
        assert "Willingness-to-Pay" in call["user_prompt"]

    @pytest.mark.asyncio
    async def test_custom_segment_ids_used(self):
        provider = MockProvider()
        provider.queue(IdeaList(ideas=[]))
        pipeline = AnalysisPipeline(provider)

        await pipeline.synthesize(
            [_gap()], Domain.SOFTWARE_SAAS, segment_ids=["parents", "fitness"]
        )

        call = provider.calls[0]
        assert "Parents" in call["user_prompt"] or "Fitness" in call["user_prompt"]

    @pytest.mark.asyncio
    async def test_count_appears_in_prompt(self):
        provider = MockProvider()
        provider.queue(IdeaList(ideas=[]))
        pipeline = AnalysisPipeline(provider)

        await pipeline.synthesize([_gap()], Domain.SOFTWARE_SAAS, count=7)

        assert "7" in provider.calls[0]["user_prompt"]

    @pytest.mark.asyncio
    async def test_uses_idealist_response_type(self):
        provider = MockProvider()
        provider.queue(IdeaList(ideas=[]))
        pipeline = AnalysisPipeline(provider)

        await pipeline.synthesize([_gap()], Domain.SOFTWARE_SAAS)

        assert provider.calls[0]["response_type"] is IdeaList


# ---------------------------------------------------------------------------
# refine()
# ---------------------------------------------------------------------------

class TestRefine:
    @pytest.mark.asyncio
    async def test_returns_idea_reports(self):
        report = _idea_report()
        provider = MockProvider()
        provider.queue(IdeaReportList(reports=[report]))
        pipeline = AnalysisPipeline(provider)

        result = await pipeline.refine([_idea()])

        assert len(result) == 1
        assert result[0].idea.title == "SpeedApp"

    @pytest.mark.asyncio
    async def test_includes_wtp_segment_context(self):
        provider = MockProvider()
        provider.queue(IdeaReportList(reports=[]))
        pipeline = AnalysisPipeline(provider)

        await pipeline.refine([_idea()])

        call = provider.calls[0]
        assert "Willingness-to-Pay" in call["user_prompt"]

    @pytest.mark.asyncio
    async def test_idea_titles_in_prompt(self):
        provider = MockProvider()
        provider.queue(IdeaReportList(reports=[]))
        pipeline = AnalysisPipeline(provider)

        await pipeline.refine([_idea("MyUniqueApp")])

        assert "MyUniqueApp" in provider.calls[0]["user_prompt"]

    @pytest.mark.asyncio
    async def test_custom_segment_ids(self):
        provider = MockProvider()
        provider.queue(IdeaReportList(reports=[]))
        pipeline = AnalysisPipeline(provider)

        await pipeline.refine([_idea()], segment_ids=["small_business"])

        call = provider.calls[0]
        assert "Small Business" in call["user_prompt"]

    @pytest.mark.asyncio
    async def test_uses_ideareportlist_response_type(self):
        provider = MockProvider()
        provider.queue(IdeaReportList(reports=[]))
        pipeline = AnalysisPipeline(provider)

        await pipeline.refine([_idea()])

        assert provider.calls[0]["response_type"] is IdeaReportList


# ---------------------------------------------------------------------------
# Prompt override directory
# ---------------------------------------------------------------------------

class TestPromptOverride:
    @pytest.mark.asyncio
    async def test_override_dir_passed_to_prompts(self, tmp_path: Path):
        override_dir = tmp_path / "prompts"
        override_dir.mkdir()
        # Write an override for analyze_trends
        (override_dir / "analyze_trends.txt").write_text("CUSTOM OVERRIDE PROMPT")

        provider = MockProvider()
        provider.queue(PainPointList(pain_points=[]))
        pipeline = AnalysisPipeline(provider, prompt_override_dir=override_dir)

        await pipeline.analyze([_trending_item()], Domain.SOFTWARE_SAAS)

        call = provider.calls[0]
        # The override returns (None, override_text) so system is None
        assert call["system_prompt"] is None
        assert call["user_prompt"] == "CUSTOM OVERRIDE PROMPT"

    @pytest.mark.asyncio
    async def test_no_override_uses_default(self, tmp_path: Path):
        override_dir = tmp_path / "prompts"
        override_dir.mkdir()
        # No file written — default prompt should be used

        provider = MockProvider()
        provider.queue(PainPointList(pain_points=[]))
        pipeline = AnalysisPipeline(provider, prompt_override_dir=override_dir)

        await pipeline.analyze([_trending_item(title="MyTitle")], Domain.SOFTWARE_SAAS)

        call = provider.calls[0]
        assert "MyTitle" in call["user_prompt"]  # Default prompt includes item title

    @pytest.mark.asyncio
    async def test_none_override_dir_uses_default(self):
        provider = MockProvider()
        provider.queue(GapList(gaps=[]))
        pipeline = AnalysisPipeline(provider, prompt_override_dir=None)

        await pipeline.identify_gaps([_pain_point("unique_pain_xyz")], Domain.SOFTWARE_SAAS)

        assert "unique_pain_xyz" in provider.calls[0]["user_prompt"]
