"""Comprehensive tests for ideagen.core.models."""
from __future__ import annotations

import asyncio
from datetime import datetime

import pytest
from pydantic import ValidationError

from ideagen.core.models import (
    CancellationToken,
    Domain,
    FeasibilityScore,
    GapAnalysis,
    Idea,
    IdeaGenerated,
    IdeaReport,
    MarketAnalysis,
    MonetizationAngle,
    PainPoint,
    PipelineComplete,
    PipelineEvent,
    RunResult,
    SourceFailed,
    StageCompleted,
    StageStarted,
    TrendingItem,
    WTPScoringCriteria,
    WTPSegment,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_idea() -> Idea:
    return Idea(
        title="AI-powered resume builder",
        problem_statement="Job seekers struggle to tailor resumes for ATS systems.",
        solution="Use LLMs to rewrite resumes per job description.",
        domain=Domain.SOFTWARE_SAAS,
        novelty_score=7.5,
    )


@pytest.fixture()
def sample_market_analysis() -> MarketAnalysis:
    return MarketAnalysis(
        target_audience="Recent graduates and career switchers",
        market_size_estimate="$2B annually",
        competitors=["Resume.io", "Zety"],
        differentiation="Real-time ATS scoring with LLM suggestions",
    )


@pytest.fixture()
def sample_feasibility() -> FeasibilityScore:
    return FeasibilityScore(
        complexity=5,
        time_to_mvp="3 months",
        suggested_tech_stack=["Python", "FastAPI", "OpenAI"],
        risks=["API rate limits", "Cost per request"],
    )


@pytest.fixture()
def sample_monetization() -> MonetizationAngle:
    return MonetizationAngle(
        revenue_model="SaaS subscription",
        pricing_strategy="Freemium with $9.99/month pro tier",
        estimated_revenue_potential="$500K ARR at 5K customers",
    )


@pytest.fixture()
def sample_idea_report(
    sample_idea,
    sample_market_analysis,
    sample_feasibility,
    sample_monetization,
) -> IdeaReport:
    return IdeaReport(
        idea=sample_idea,
        market_analysis=sample_market_analysis,
        feasibility=sample_feasibility,
        monetization=sample_monetization,
    )


@pytest.fixture()
def sample_run_result(sample_idea_report) -> RunResult:
    return RunResult(
        ideas=[sample_idea_report],
        sources_used=["HackerNews", "Reddit"],
        domain=Domain.SOFTWARE_SAAS,
    )


# ---------------------------------------------------------------------------
# Domain enum
# ---------------------------------------------------------------------------


class TestDomain:
    def test_has_software_saas_value(self):
        assert Domain.SOFTWARE_SAAS == "SOFTWARE_SAAS"

    def test_has_broad_business_value(self):
        assert Domain.BROAD_BUSINESS == "BROAD_BUSINESS"

    def test_has_content_media_value(self):
        assert Domain.CONTENT_MEDIA == "CONTENT_MEDIA"

    def test_is_str_subclass(self):
        assert issubclass(Domain, str)

    def test_has_exactly_three_members(self):
        assert len(Domain) == 3

    def test_member_is_string_instance(self):
        assert isinstance(Domain.SOFTWARE_SAAS, str)


# ---------------------------------------------------------------------------
# WTPSegment
# ---------------------------------------------------------------------------


class TestWTPSegment:
    def test_instantiates_with_valid_data(self):
        segment = WTPSegment(
            id="seg-1",
            name="Power Users",
            emotional_driver="Fear of missing out on productivity gains",
            spending_areas=["SaaS tools", "Online courses"],
            pain_tolerance=3.5,
            wtp_score=0.82,
        )
        assert segment.id == "seg-1"
        assert segment.name == "Power Users"
        assert segment.emotional_driver == "Fear of missing out on productivity gains"
        assert segment.spending_areas == ["SaaS tools", "Online courses"]
        assert segment.pain_tolerance == 3.5
        assert segment.wtp_score == 0.82

    def test_raises_on_missing_required_fields(self):
        with pytest.raises(ValidationError):
            WTPSegment(id="seg-1", name="Power Users")  # type: ignore[call-arg]

    def test_raises_on_wrong_type_for_wtp_score(self):
        with pytest.raises(ValidationError):
            WTPSegment(
                id="seg-1",
                name="Power Users",
                emotional_driver="FOMO",
                spending_areas=[],
                pain_tolerance=3.0,
                wtp_score="high",  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# WTPScoringCriteria
# ---------------------------------------------------------------------------


class TestWTPScoringCriteria:
    def test_default_weights_sum_to_one(self):
        criteria = WTPScoringCriteria()
        total = (
            criteria.emotional_intensity
            + criteria.pain_frequency
            + criteria.price_insensitivity
            + criteria.market_size
            + criteria.accessibility
            + criteria.defensibility
        )
        assert abs(total - 1.0) < 1e-9

    def test_default_emotional_intensity(self):
        assert WTPScoringCriteria().emotional_intensity == 0.25

    def test_default_pain_frequency(self):
        assert WTPScoringCriteria().pain_frequency == 0.20

    def test_default_price_insensitivity(self):
        assert WTPScoringCriteria().price_insensitivity == 0.20

    def test_default_market_size(self):
        assert WTPScoringCriteria().market_size == 0.15

    def test_default_accessibility(self):
        assert WTPScoringCriteria().accessibility == 0.10

    def test_default_defensibility(self):
        assert WTPScoringCriteria().defensibility == 0.10


# ---------------------------------------------------------------------------
# TrendingItem
# ---------------------------------------------------------------------------


class TestTrendingItem:
    def _make(self, **overrides):
        defaults = dict(
            title="Show HN: My new tool",
            url="https://news.ycombinator.com/item?id=1234",
            source="hackernews",
            timestamp=datetime(2026, 3, 7, 12, 0, 0),
        )
        defaults.update(overrides)
        return TrendingItem(**defaults)

    def test_creates_with_valid_data(self):
        item = self._make()
        assert item.title == "Show HN: My new tool"
        assert item.url == "https://news.ycombinator.com/item?id=1234"
        assert item.source == "hackernews"

    def test_default_score_is_zero(self):
        item = self._make()
        assert item.score == 0

    def test_default_metadata_is_empty_dict(self):
        item = self._make()
        assert item.metadata == {}

    def test_default_comment_count_is_zero(self):
        item = self._make()
        assert item.comment_count == 0

    def test_explicit_score_stored_correctly(self):
        item = self._make(score=42)
        assert item.score == 42

    def test_explicit_metadata_stored_correctly(self):
        item = self._make(metadata={"rank": 1})
        assert item.metadata == {"rank": 1}

    def test_explicit_comment_count_stored_correctly(self):
        item = self._make(comment_count=100)
        assert item.comment_count == 100

    def test_is_frozen_title(self):
        item = self._make()
        with pytest.raises(Exception):
            item.title = "mutated"  # type: ignore[misc]

    def test_is_frozen_score(self):
        item = self._make()
        with pytest.raises(Exception):
            item.score = 999  # type: ignore[misc]

    def test_json_round_trip(self):
        item = self._make(score=10, comment_count=5, metadata={"key": "value"})
        serialized = item.model_dump_json()
        restored = TrendingItem.model_validate_json(serialized)
        assert restored == item

    def test_json_round_trip_preserves_timestamp(self):
        ts = datetime(2026, 3, 7, 12, 0, 0)
        item = self._make(timestamp=ts)
        restored = TrendingItem.model_validate_json(item.model_dump_json())
        assert restored.timestamp == ts


# ---------------------------------------------------------------------------
# PainPoint
# ---------------------------------------------------------------------------


class TestPainPoint:
    def test_creates_with_valid_data(self):
        pp = PainPoint(
            description="Slow build times frustrate developers",
            frequency="daily",
            severity=8.0,
        )
        assert pp.description == "Slow build times frustrate developers"
        assert pp.frequency == "daily"
        assert pp.severity == 8.0

    def test_default_source_items_is_empty_list(self):
        pp = PainPoint(
            description="Slow build times",
            frequency="daily",
            severity=8.0,
        )
        assert pp.source_items == []

    def test_source_items_stored_when_provided(self):
        pp = PainPoint(
            description="Slow build times",
            frequency="daily",
            severity=8.0,
            source_items=["hn-1234", "reddit-5678"],
        )
        assert pp.source_items == ["hn-1234", "reddit-5678"]

    def test_is_frozen(self):
        pp = PainPoint(description="Slow build times", frequency="daily", severity=8.0)
        with pytest.raises(Exception):
            pp.description = "mutated"  # type: ignore[misc]

    def test_raises_on_missing_required_fields(self):
        with pytest.raises(ValidationError):
            PainPoint(description="only desc")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# GapAnalysis
# ---------------------------------------------------------------------------


class TestGapAnalysis:
    def test_creates_with_valid_data(self):
        gap = GapAnalysis(
            description="No affordable CI/CD for solo devs",
            evidence=["Reddit post #1", "HN thread #2"],
            affected_audience="Solo indie hackers",
        )
        assert gap.description == "No affordable CI/CD for solo devs"
        assert gap.evidence == ["Reddit post #1", "HN thread #2"]
        assert gap.affected_audience == "Solo indie hackers"

    def test_default_opportunity_size_is_unknown(self):
        gap = GapAnalysis(
            description="Gap",
            evidence=["evidence"],
            affected_audience="Devs",
        )
        assert gap.opportunity_size == "unknown"

    def test_explicit_opportunity_size_stored_correctly(self):
        gap = GapAnalysis(
            description="Gap",
            evidence=["evidence"],
            affected_audience="Devs",
            opportunity_size="$10M TAM",
        )
        assert gap.opportunity_size == "$10M TAM"

    def test_is_frozen(self):
        gap = GapAnalysis(
            description="Gap",
            evidence=["evidence"],
            affected_audience="Devs",
        )
        with pytest.raises(Exception):
            gap.description = "mutated"  # type: ignore[misc]

    def test_raises_on_missing_required_fields(self):
        with pytest.raises(ValidationError):
            GapAnalysis(description="only desc")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Idea
# ---------------------------------------------------------------------------


class TestIdea:
    def test_creates_with_valid_data(self, sample_idea):
        assert sample_idea.title == "AI-powered resume builder"
        assert sample_idea.domain == Domain.SOFTWARE_SAAS
        assert sample_idea.novelty_score == 7.5

    def test_default_content_hash_is_empty_string(self, sample_idea):
        assert sample_idea.content_hash == ""

    def test_default_tags_is_empty_list(self, sample_idea):
        assert sample_idea.tags == []

    def test_explicit_content_hash_stored(self):
        idea = Idea(
            title="Idea",
            problem_statement="Problem",
            solution="Solution",
            domain=Domain.BROAD_BUSINESS,
            novelty_score=5.0,
            content_hash="abc123",
        )
        assert idea.content_hash == "abc123"

    def test_explicit_tags_stored(self):
        idea = Idea(
            title="Idea",
            problem_statement="Problem",
            solution="Solution",
            domain=Domain.CONTENT_MEDIA,
            novelty_score=5.0,
            tags=["ai", "saas"],
        )
        assert idea.tags == ["ai", "saas"]

    def test_raises_on_invalid_domain(self):
        with pytest.raises(ValidationError):
            Idea(
                title="Idea",
                problem_statement="Problem",
                solution="Solution",
                domain="INVALID_DOMAIN",  # type: ignore[arg-type]
                novelty_score=5.0,
            )

    def test_raises_on_missing_required_fields(self):
        with pytest.raises(ValidationError):
            Idea(title="Only title")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# MarketAnalysis
# ---------------------------------------------------------------------------


class TestMarketAnalysis:
    def test_creates_with_valid_data(self, sample_market_analysis):
        assert sample_market_analysis.target_audience == "Recent graduates and career switchers"
        assert sample_market_analysis.market_size_estimate == "$2B annually"
        assert sample_market_analysis.differentiation == "Real-time ATS scoring with LLM suggestions"

    def test_default_competitors_is_empty_list(self):
        ma = MarketAnalysis(
            target_audience="Devs",
            market_size_estimate="$1B",
            differentiation="Unique angle",
        )
        assert ma.competitors == []

    def test_explicit_competitors_stored(self, sample_market_analysis):
        assert sample_market_analysis.competitors == ["Resume.io", "Zety"]

    def test_raises_on_missing_required_fields(self):
        with pytest.raises(ValidationError):
            MarketAnalysis(target_audience="Devs")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# FeasibilityScore
# ---------------------------------------------------------------------------


class TestFeasibilityScore:
    def test_creates_with_valid_data(self, sample_feasibility):
        assert sample_feasibility.complexity == 5
        assert sample_feasibility.time_to_mvp == "3 months"

    def test_default_suggested_tech_stack_is_empty_list(self):
        fs = FeasibilityScore(complexity=3, time_to_mvp="1 month")
        assert fs.suggested_tech_stack == []

    def test_default_risks_is_empty_list(self):
        fs = FeasibilityScore(complexity=3, time_to_mvp="1 month")
        assert fs.risks == []

    def test_explicit_tech_stack_and_risks_stored(self, sample_feasibility):
        assert sample_feasibility.suggested_tech_stack == ["Python", "FastAPI", "OpenAI"]
        assert sample_feasibility.risks == ["API rate limits", "Cost per request"]

    def test_raises_on_missing_required_fields(self):
        with pytest.raises(ValidationError):
            FeasibilityScore(complexity=5)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# MonetizationAngle
# ---------------------------------------------------------------------------


class TestMonetizationAngle:
    def test_creates_with_valid_data(self, sample_monetization):
        assert sample_monetization.revenue_model == "SaaS subscription"
        assert sample_monetization.pricing_strategy == "Freemium with $9.99/month pro tier"
        assert sample_monetization.estimated_revenue_potential == "$500K ARR at 5K customers"

    def test_raises_on_missing_required_fields(self):
        with pytest.raises(ValidationError):
            MonetizationAngle(revenue_model="SaaS")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# IdeaReport
# ---------------------------------------------------------------------------


class TestIdeaReport:
    def test_creates_with_all_sub_models(self, sample_idea_report):
        assert sample_idea_report.idea.title == "AI-powered resume builder"
        assert sample_idea_report.market_analysis.market_size_estimate == "$2B annually"
        assert sample_idea_report.feasibility.complexity == 5
        assert sample_idea_report.monetization.revenue_model == "SaaS subscription"

    def test_default_wtp_score_is_zero(self, sample_idea_report):
        assert sample_idea_report.wtp_score == 0.0

    def test_default_target_segments_is_empty_list(self, sample_idea_report):
        assert sample_idea_report.target_segments == []

    def test_generated_at_auto_set(self, sample_idea_report):
        assert isinstance(sample_idea_report.generated_at, datetime)

    def test_generated_at_is_recent(self, sample_idea_report):
        now = datetime.now()
        diff = abs((now - sample_idea_report.generated_at).total_seconds())
        assert diff < 5.0

    def test_explicit_wtp_score_stored(
        self,
        sample_idea,
        sample_market_analysis,
        sample_feasibility,
        sample_monetization,
    ):
        report = IdeaReport(
            idea=sample_idea,
            market_analysis=sample_market_analysis,
            feasibility=sample_feasibility,
            monetization=sample_monetization,
            wtp_score=0.78,
        )
        assert report.wtp_score == 0.78

    def test_target_segments_stored_when_provided(
        self,
        sample_idea,
        sample_market_analysis,
        sample_feasibility,
        sample_monetization,
    ):
        segment = WTPSegment(
            id="seg-1",
            name="Power Users",
            emotional_driver="FOMO",
            spending_areas=["SaaS"],
            pain_tolerance=3.0,
            wtp_score=0.9,
        )
        report = IdeaReport(
            idea=sample_idea,
            market_analysis=sample_market_analysis,
            feasibility=sample_feasibility,
            monetization=sample_monetization,
            target_segments=[segment],
        )
        assert len(report.target_segments) == 1
        assert report.target_segments[0].id == "seg-1"

    def test_model_json_schema_produces_valid_schema(self, sample_idea_report):
        schema = IdeaReport.model_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema or "$defs" in schema or "title" in schema

    def test_raises_on_missing_required_fields(self):
        with pytest.raises(ValidationError):
            IdeaReport(idea=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RunResult
# ---------------------------------------------------------------------------


class TestRunResult:
    def test_creates_with_composite_data(self, sample_run_result):
        assert len(sample_run_result.ideas) == 1
        assert sample_run_result.sources_used == ["HackerNews", "Reddit"]
        assert sample_run_result.domain == Domain.SOFTWARE_SAAS

    def test_default_content_hash_is_empty_string(self, sample_run_result):
        assert sample_run_result.content_hash == ""

    def test_default_total_items_scraped_is_zero(self, sample_run_result):
        assert sample_run_result.total_items_scraped == 0

    def test_default_total_after_dedup_is_zero(self, sample_run_result):
        assert sample_run_result.total_after_dedup == 0

    def test_timestamp_auto_set(self, sample_run_result):
        assert isinstance(sample_run_result.timestamp, datetime)

    def test_timestamp_is_recent(self, sample_run_result):
        now = datetime.now()
        diff = abs((now - sample_run_result.timestamp).total_seconds())
        assert diff < 5.0

    def test_default_config_snapshot_is_empty_dict(self, sample_run_result):
        assert sample_run_result.config_snapshot == {}

    def test_explicit_totals_stored(self, sample_idea_report):
        result = RunResult(
            ideas=[sample_idea_report],
            sources_used=["HackerNews"],
            domain=Domain.SOFTWARE_SAAS,
            total_items_scraped=50,
            total_after_dedup=30,
        )
        assert result.total_items_scraped == 50
        assert result.total_after_dedup == 30

    def test_explicit_content_hash_stored(self, sample_idea_report):
        result = RunResult(
            ideas=[sample_idea_report],
            sources_used=["HackerNews"],
            domain=Domain.SOFTWARE_SAAS,
            content_hash="deadbeef",
        )
        assert result.content_hash == "deadbeef"


# ---------------------------------------------------------------------------
# PipelineEvent hierarchy
# ---------------------------------------------------------------------------


class TestStageStarted:
    def test_event_type_is_stage_started(self):
        event = StageStarted(stage="scraping")
        assert event.event_type == "stage_started"

    def test_stage_stored_correctly(self):
        event = StageStarted(stage="analysis")
        assert event.stage == "analysis"

    def test_default_metadata_is_empty_dict(self):
        event = StageStarted(stage="scraping")
        assert event.metadata == {}

    def test_timestamp_auto_set(self):
        event = StageStarted(stage="scraping")
        assert isinstance(event.timestamp, datetime)

    def test_is_frozen(self):
        event = StageStarted(stage="scraping")
        with pytest.raises(Exception):
            event.stage = "mutated"  # type: ignore[misc]

    def test_is_pipeline_event_subclass(self):
        assert isinstance(StageStarted(stage="scraping"), PipelineEvent)


class TestStageCompleted:
    def test_event_type_is_stage_completed(self):
        event = StageCompleted(stage="scraping", duration_ms=1500)
        assert event.event_type == "stage_completed"

    def test_duration_ms_stored(self):
        event = StageCompleted(stage="scraping", duration_ms=1500)
        assert event.duration_ms == 1500

    def test_stage_stored(self):
        event = StageCompleted(stage="analysis", duration_ms=200)
        assert event.stage == "analysis"

    def test_default_metadata_is_empty_dict(self):
        event = StageCompleted(stage="scraping", duration_ms=100)
        assert event.metadata == {}

    def test_is_frozen(self):
        event = StageCompleted(stage="scraping", duration_ms=100)
        with pytest.raises(Exception):
            event.duration_ms = 0  # type: ignore[misc]


class TestSourceFailed:
    def test_event_type_is_source_failed(self):
        event = SourceFailed(source="hackernews", error="Connection timeout")
        assert event.event_type == "source_failed"

    def test_source_and_error_stored(self):
        event = SourceFailed(source="reddit", error="Rate limited")
        assert event.source == "reddit"
        assert event.error == "Rate limited"

    def test_is_frozen(self):
        event = SourceFailed(source="hackernews", error="timeout")
        with pytest.raises(Exception):
            event.error = "mutated"  # type: ignore[misc]


class TestIdeaGenerated:
    def test_event_type_is_idea_generated(self, sample_idea):
        event = IdeaGenerated(idea=sample_idea, index=0, total=5)
        assert event.event_type == "idea_generated"

    def test_idea_index_total_stored(self, sample_idea):
        event = IdeaGenerated(idea=sample_idea, index=2, total=10)
        assert event.idea == sample_idea
        assert event.index == 2
        assert event.total == 10

    def test_is_frozen(self, sample_idea):
        event = IdeaGenerated(idea=sample_idea, index=0, total=5)
        with pytest.raises(Exception):
            event.index = 99  # type: ignore[misc]


class TestPipelineComplete:
    def test_event_type_is_pipeline_complete(self, sample_run_result):
        event = PipelineComplete(result=sample_run_result)
        assert event.event_type == "pipeline_complete"

    def test_result_stored(self, sample_run_result):
        event = PipelineComplete(result=sample_run_result)
        assert event.result is sample_run_result

    def test_is_frozen(self, sample_run_result):
        event = PipelineComplete(result=sample_run_result)
        with pytest.raises(Exception):
            event.event_type = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CancellationToken
# ---------------------------------------------------------------------------


class TestCancellationToken:
    def test_initial_state_is_not_cancelled(self):
        token = CancellationToken()
        assert token.is_cancelled is False

    def test_cancel_sets_is_cancelled(self):
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled is True

    def test_cancel_is_idempotent(self):
        token = CancellationToken()
        token.cancel()
        token.cancel()
        assert token.is_cancelled is True

    @pytest.mark.asyncio
    async def test_wait_with_timeout_returns_false_when_not_cancelled(self):
        token = CancellationToken()
        result = await token.wait(timeout=0.05)
        assert result is False

    @pytest.mark.asyncio
    async def test_wait_returns_true_when_already_cancelled(self):
        token = CancellationToken()
        token.cancel()
        result = await token.wait(timeout=1.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_returns_true_when_cancelled_concurrently(self):
        token = CancellationToken()

        async def cancel_after_delay():
            await asyncio.sleep(0.05)
            token.cancel()

        asyncio.create_task(cancel_after_delay())
        result = await token.wait(timeout=2.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_without_timeout_returns_true_when_cancelled(self):
        token = CancellationToken()

        async def do_wait():
            return await token.wait()

        task = asyncio.create_task(do_wait())
        await asyncio.sleep(0.02)
        token.cancel()
        result = await task
        assert result is True


# ---------------------------------------------------------------------------
# Validation edge cases
# ---------------------------------------------------------------------------


class TestValidation:
    def test_trending_item_raises_on_wrong_type_for_score(self):
        with pytest.raises(ValidationError):
            TrendingItem(
                title="Test",
                url="https://example.com",
                source="test",
                timestamp=datetime.now(),
                score="not-an-int",  # type: ignore[arg-type]
            )

    def test_pain_point_raises_on_wrong_type_for_severity(self):
        with pytest.raises(ValidationError):
            PainPoint(
                description="Desc",
                frequency="daily",
                severity="high",  # type: ignore[arg-type]
            )

    def test_idea_raises_on_wrong_type_for_novelty_score(self):
        with pytest.raises(ValidationError):
            Idea(
                title="Idea",
                problem_statement="Problem",
                solution="Solution",
                domain=Domain.SOFTWARE_SAAS,
                novelty_score="very novel",  # type: ignore[arg-type]
            )

    def test_feasibility_raises_on_wrong_type_for_complexity(self):
        with pytest.raises(ValidationError):
            FeasibilityScore(
                complexity="hard",  # type: ignore[arg-type]
                time_to_mvp="3 months",
            )

    def test_wtp_segment_raises_on_wrong_type_for_pain_tolerance(self):
        with pytest.raises(ValidationError):
            WTPSegment(
                id="seg-1",
                name="Segment",
                emotional_driver="driver",
                spending_areas=[],
                pain_tolerance="medium",  # type: ignore[arg-type]
                wtp_score=0.5,
            )

    def test_run_result_raises_on_missing_domain(self, sample_idea_report):
        with pytest.raises(ValidationError):
            RunResult(
                ideas=[sample_idea_report],
                sources_used=["HN"],
            )  # type: ignore[call-arg]

    def test_gap_analysis_raises_on_missing_evidence(self):
        with pytest.raises(ValidationError):
            GapAnalysis(
                description="A gap",
                affected_audience="Devs",
            )  # type: ignore[call-arg]
