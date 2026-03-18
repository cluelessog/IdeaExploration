"""Tests for IdeaGenService orchestrator."""
from __future__ import annotations
from datetime import datetime
from typing import TypeVar

import pytest
from pydantic import BaseModel

from ideagen.core.config import IdeaGenConfig, GenerationConfig
from ideagen.core.exceptions import SourceUnavailableError
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
    SourceFailed,
    StageCompleted,
    StageStarted,
    TrendingItem,
    RunResult,
)
from ideagen.core.pipeline import GapList, IdeaList, IdeaReportList, PainPointList
from ideagen.core.service import IdeaGenService
from ideagen.providers.base import AIProvider
from ideagen.sources.base import DataSource
from ideagen.storage.base import StorageBackend

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Mock implementations
# ---------------------------------------------------------------------------

class MockSource(DataSource):
    """DataSource that returns pre-configured items or raises on demand."""

    def __init__(self, name_: str, items: list[TrendingItem] | None = None, fail: bool = False):
        self._name = name_
        self._items = items or []
        self._fail = fail

    @property
    def name(self) -> str:
        return self._name

    async def collect(self, domain: Domain, limit: int = 50) -> list[TrendingItem]:
        if self._fail:
            raise RuntimeError(f"Source {self._name} is unavailable")
        return self._items

    async def is_available(self) -> bool:
        return not self._fail


class FailingSource(DataSource):
    """DataSource that always raises SourceUnavailableError."""

    def __init__(self, name_: str, error_msg: str = "source unavailable"):
        self._name = name_
        self._error_msg = error_msg

    @property
    def name(self) -> str:
        return self._name

    async def collect(self, domain: Domain, limit: int = 50) -> list[TrendingItem]:
        raise SourceUnavailableError(self._error_msg)

    async def is_available(self) -> bool:
        return False


class MockProvider(AIProvider):
    """Configurable mock that returns pre-built Pydantic models in FIFO order."""

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


class MockStorage(StorageBackend):
    """In-memory storage backend for testing."""

    def __init__(self):
        self.saved: list[RunResult] = []

    async def save_run(self, result: RunResult) -> str:
        self.saved.append(result)
        return "mock-run-id"

    async def get_runs(self, offset: int = 0, limit: int = 20, **filters) -> list[dict]:
        return []

    async def get_idea(self, idea_id: str) -> IdeaReport | None:
        return None

    async def search_ideas(self, query: str, offset: int = 0, limit: int = 50) -> list[IdeaReport]:
        return []

    async def get_run_detail(self, run_id_prefix: str) -> dict | None:
        return None

    async def save_scrape_cache(self, batch_id: str, source: str, items: list) -> None:
        pass

    async def load_latest_scrape_cache(self, source_names: list[str] | None = None) -> list:
        return []

    async def find_runs_by_content_hash(self, content_hash: str, exclude_id: str | None = None) -> list[dict]:
        return []

    async def find_runs_by_prefix(self, prefix: str) -> list[dict]:
        return []

    async def get_runs_count(self, **filters) -> int:
        return 0


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _trending_item(title: str = "Test SaaS Tool", score: int = 100, source: str = "hackernews") -> TrendingItem:
    return TrendingItem(
        title=title,
        url="https://example.com",
        score=score,
        source=source,
        timestamp=datetime(2024, 1, 1),
        comment_count=10,
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
        problem_statement="It is too slow",
        solution="Make it fast",
        domain=Domain.SOFTWARE_SAAS,
        novelty_score=8.0,
    )


def _idea_report(title: str = "SpeedApp") -> IdeaReport:
    return IdeaReport(
        idea=_idea(title),
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


def _queue_full_pipeline(provider: MockProvider, idea_titles: list[str] | None = None) -> None:
    """Queue the four LLM responses needed for a full pipeline run."""
    titles = idea_titles or ["SpeedApp"]
    provider.queue(PainPointList(pain_points=[_pain_point()]))
    provider.queue(GapList(gaps=[_gap()]))
    provider.queue(IdeaList(ideas=[_idea(t) for t in titles]))
    provider.queue(IdeaReportList(reports=[_idea_report(t) for t in titles]))


async def _collect_events(service: IdeaGenService, **kwargs) -> list[PipelineEvent]:
    events: list[PipelineEvent] = []
    async for event in service.run(**kwargs):
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Full pipeline event sequence
# ---------------------------------------------------------------------------

class TestFullPipelineEventSequence:
    async def test_yields_correct_stage_sequence(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service)

        stage_events = [e for e in events if isinstance(e, (StageStarted, StageCompleted))]
        stage_names = [(type(e).__name__, e.stage) for e in stage_events]

        assert ("StageStarted", "collect") in stage_names
        assert ("StageCompleted", "collect") in stage_names
        assert ("StageStarted", "dedup") in stage_names
        assert ("StageCompleted", "dedup") in stage_names
        assert ("StageStarted", "analyze") in stage_names
        assert ("StageCompleted", "analyze") in stage_names
        assert ("StageStarted", "identify_gaps") in stage_names
        assert ("StageCompleted", "identify_gaps") in stage_names
        assert ("StageStarted", "synthesize") in stage_names
        assert ("StageCompleted", "synthesize") in stage_names
        assert ("StageStarted", "refine") in stage_names
        assert ("StageCompleted", "refine") in stage_names

    async def test_pipeline_complete_is_last_event(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service)

        assert isinstance(events[-1], PipelineComplete)

    async def test_idea_generated_events_emitted(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider, idea_titles=["AppA", "AppB"])

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service)

        idea_events = [e for e in events if isinstance(e, IdeaGenerated)]
        assert len(idea_events) == 2
        assert idea_events[0].index == 0
        assert idea_events[0].total == 2
        assert idea_events[1].index == 1

    async def test_started_before_completed_for_each_stage(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service)

        stage_events = [e for e in events if isinstance(e, (StageStarted, StageCompleted))]
        # For each stage, StageStarted should appear before StageCompleted
        for stage in ("collect", "dedup", "analyze", "identify_gaps", "synthesize", "refine"):
            started_idx = next(
                i for i, e in enumerate(stage_events)
                if isinstance(e, StageStarted) and e.stage == stage
            )
            completed_idx = next(
                i for i, e in enumerate(stage_events)
                if isinstance(e, StageCompleted) and e.stage == stage
            )
            assert started_idx < completed_idx

    async def test_pipeline_complete_contains_run_result(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider, idea_titles=["SpeedApp"])

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service)

        complete = next(e for e in events if isinstance(e, PipelineComplete))
        assert complete.result.domain == Domain.SOFTWARE_SAAS
        assert len(complete.result.ideas) == 1
        assert complete.result.ideas[0].idea.title == "SpeedApp"

    async def test_run_result_has_content_hash(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service)

        complete = next(e for e in events if isinstance(e, PipelineComplete))
        assert complete.result.content_hash != ""


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------

class TestDryRun:
    async def test_dry_run_stops_after_dedup(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service, dry_run=True)

        stage_names = [e.stage for e in events if isinstance(e, StageStarted)]
        assert "collect" in stage_names
        assert "dedup" in stage_names
        assert "analyze" not in stage_names
        assert "synthesize" not in stage_names

    async def test_dry_run_returns_empty_ideas(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service, dry_run=True)

        complete = next(e for e in events if isinstance(e, PipelineComplete))
        assert complete.result.ideas == []

    async def test_dry_run_records_total_after_dedup(self):
        titles = ["Quantum Computing Startup", "AI-Powered Healthcare", "Blockchain Voting Platform",
                   "Solar Energy Marketplace", "Robot Delivery Service"]
        items = [_trending_item(t) for t in titles]
        source = MockSource("hackernews", items)
        provider = MockProvider()

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service, dry_run=True)

        complete = next(e for e in events if isinstance(e, PipelineComplete))
        assert complete.result.total_after_dedup == 5

    async def test_dry_run_no_llm_calls(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        await _collect_events(service, dry_run=True)

        assert provider.calls == []


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------

class TestCancellation:
    async def test_cancellation_after_collect_stops_pipeline(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()

        token = CancellationToken()
        token.cancel()  # cancelled before pipeline starts

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service, cancellation_token=token)

        stage_names = [e.stage for e in events if isinstance(e, StageStarted)]
        # collect and dedup run before first cancellation check
        assert "collect" in stage_names
        assert "analyze" not in stage_names

    async def test_cancellation_stops_before_analyze(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()

        token = CancellationToken()
        token.cancel()

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service, cancellation_token=token)

        # No LLM calls should have been made
        assert provider.calls == []

    async def test_no_pipeline_complete_when_cancelled_early(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()

        token = CancellationToken()
        token.cancel()

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service, cancellation_token=token)

        complete_events = [e for e in events if isinstance(e, PipelineComplete)]
        assert complete_events == []

    async def test_no_cancellation_token_runs_to_completion(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service, cancellation_token=None)

        assert isinstance(events[-1], PipelineComplete)


# ---------------------------------------------------------------------------
# Partial source failure
# ---------------------------------------------------------------------------

class TestPartialSourceFailure:
    async def test_one_failing_source_continues_pipeline(self):
        good = MockSource("hackernews", [_trending_item("Good item")])
        bad = MockSource("reddit", fail=True)
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(
            sources={"hackernews": good, "reddit": bad},
            provider=provider,
        )
        events = await _collect_events(service)

        # Pipeline should complete successfully
        assert isinstance(events[-1], PipelineComplete)

    async def test_items_from_good_source_used(self):
        good = MockSource("hackernews", [_trending_item("Good item")])
        bad = MockSource("reddit", fail=True)
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(
            sources={"hackernews": good, "reddit": bad},
            provider=provider,
        )
        events = await _collect_events(service)

        collect_completed = next(
            e for e in events
            if isinstance(e, StageCompleted) and e.stage == "collect"
        )
        assert collect_completed.metadata["total_items"] == 1

    async def test_all_sources_fail_yields_empty_complete(self):
        bad1 = MockSource("hackernews", fail=True)
        bad2 = MockSource("reddit", fail=True)
        provider = MockProvider()

        service = IdeaGenService(
            sources={"hackernews": bad1, "reddit": bad2},
            provider=provider,
        )
        events = await _collect_events(service)

        complete = next(e for e in events if isinstance(e, PipelineComplete))
        assert complete.result.ideas == []
        assert complete.result.total_after_dedup == 0


# ---------------------------------------------------------------------------
# Zero items after dedup
# ---------------------------------------------------------------------------

class TestZeroItemsAfterDedup:
    async def test_zero_items_yields_pipeline_complete_with_empty_ideas(self):
        source = MockSource("hackernews", [])  # no items
        provider = MockProvider()

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service)

        complete = next(e for e in events if isinstance(e, PipelineComplete))
        assert complete.result.ideas == []

    async def test_zero_items_no_llm_calls(self):
        source = MockSource("hackernews", [])
        provider = MockProvider()

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        await _collect_events(service)

        assert provider.calls == []

    async def test_zero_items_dedup_stage_still_runs(self):
        source = MockSource("hackernews", [])
        provider = MockProvider()

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service)

        stage_names = [e.stage for e in events if isinstance(e, StageCompleted)]
        assert "dedup" in stage_names

    async def test_zero_items_total_after_dedup_is_zero(self):
        source = MockSource("hackernews", [])
        provider = MockProvider()

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service)

        complete = next(e for e in events if isinstance(e, PipelineComplete))
        assert complete.result.total_after_dedup == 0


# ---------------------------------------------------------------------------
# Storage integration
# ---------------------------------------------------------------------------

class TestStorage:
    async def test_storage_save_called_on_success(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)
        storage = MockStorage()

        service = IdeaGenService(
            sources={"hackernews": source},
            provider=provider,
            storage=storage,
        )
        await _collect_events(service)

        assert len(storage.saved) == 1

    async def test_store_stage_events_emitted_with_storage(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)
        storage = MockStorage()

        service = IdeaGenService(
            sources={"hackernews": source},
            provider=provider,
            storage=storage,
        )
        events = await _collect_events(service)

        stage_names = [e.stage for e in events if isinstance(e, StageStarted)]
        assert "store" in stage_names

    async def test_no_storage_no_store_stage(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(
            sources={"hackernews": source},
            provider=provider,
            storage=None,
        )
        events = await _collect_events(service)

        stage_names = [e.stage for e in events if isinstance(e, StageStarted)]
        assert "store" not in stage_names


# ---------------------------------------------------------------------------
# Config options
# ---------------------------------------------------------------------------

class TestConfigOptions:
    async def test_idea_count_forwarded_to_synthesize(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        await _collect_events(service, idea_count=7)

        # synthesize call is the 3rd provider call (analyze, identify_gaps, synthesize)
        synthesize_call = provider.calls[2]
        assert "7" in synthesize_call["user_prompt"]

    async def test_sources_used_recorded_in_result(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service)

        complete = next(e for e in events if isinstance(e, PipelineComplete))
        assert "hackernews" in complete.result.sources_used

    async def test_domain_recorded_in_result(self):
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _collect_events(service, domain=Domain.BROAD_BUSINESS)

        complete = next(e for e in events if isinstance(e, PipelineComplete))
        assert complete.result.domain == Domain.BROAD_BUSINESS


# ---------------------------------------------------------------------------
# Duplicate run detection (Phase 10.1)
# ---------------------------------------------------------------------------

class TestDuplicateRunDetection:
    async def test_duplicate_run_emits_warning_event(self):
        """When storage finds existing runs with same content hash, DuplicateRunWarning is emitted."""
        from ideagen.core.models import DuplicateRunWarning

        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        storage = MockStorage()
        # Override find_runs_by_content_hash to return a fake existing run
        async def _find_dup(content_hash, exclude_id=None):
            return [{"id": "existing-run-123", "timestamp": "2024-01-01"}]
        storage.find_runs_by_content_hash = _find_dup

        service = IdeaGenService(
            sources={"hackernews": source}, provider=provider, storage=storage,
        )
        events = await _collect_events(service)

        dup_events = [e for e in events if isinstance(e, DuplicateRunWarning)]
        assert len(dup_events) == 1
        assert "existing-run-123" in dup_events[0].existing_run_ids

    async def test_unique_run_no_warning(self):
        """No DuplicateRunWarning when content hash is unique."""
        from ideagen.core.models import DuplicateRunWarning

        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)
        storage = MockStorage()

        service = IdeaGenService(
            sources={"hackernews": source}, provider=provider, storage=storage,
        )
        events = await _collect_events(service)

        dup_events = [e for e in events if isinstance(e, DuplicateRunWarning)]
        assert len(dup_events) == 0


# ---------------------------------------------------------------------------
# Cached empty warning (Phase 10.2)
# ---------------------------------------------------------------------------

class TestCachedEmptyWarning:
    async def test_cached_empty_emits_warning_event(self):
        """CacheEmptyWarning emitted when --cached has empty cache."""
        from ideagen.core.models import CacheEmptyWarning

        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        storage = MockStorage()
        # load_latest_scrape_cache already returns [] by default

        service = IdeaGenService(
            sources={"hackernews": source}, provider=provider, storage=storage,
        )
        events = await _collect_events(service, cached=True)

        cache_events = [e for e in events if isinstance(e, CacheEmptyWarning)]
        assert len(cache_events) == 1

    async def test_cached_with_data_no_warning(self):
        """No CacheEmptyWarning when cache has data."""
        from ideagen.core.models import CacheEmptyWarning

        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)
        storage = MockStorage()

        # Override to return cached items
        async def _load_cache(source_names=None):
            return [_trending_item("Cached Item")]
        storage.load_latest_scrape_cache = _load_cache

        service = IdeaGenService(
            sources={"hackernews": source}, provider=provider, storage=storage,
        )
        events = await _collect_events(service, cached=True)

        cache_events = [e for e in events if isinstance(e, CacheEmptyWarning)]
        assert len(cache_events) == 0

    async def test_cached_empty_still_completes_pipeline(self):
        """Pipeline still completes even when cache is empty."""
        source = MockSource("hackernews", [_trending_item()])
        provider = MockProvider()
        storage = MockStorage()

        service = IdeaGenService(
            sources={"hackernews": source}, provider=provider, storage=storage,
        )
        events = await _collect_events(service, cached=True)

        complete_events = [e for e in events if isinstance(e, PipelineComplete)]
        assert len(complete_events) == 1


# ---------------------------------------------------------------------------
# SourceFailed events (Audit Finding #7)
# ---------------------------------------------------------------------------

class TestSourceFailedEvents:
    async def test_source_failed_event_yielded(self):
        """One source raises SourceUnavailableError, SourceFailed event appears in event stream."""
        good = MockSource("hackernews", [_trending_item()])
        bad = FailingSource("reddit", error_msg="connection refused")
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(
            sources={"hackernews": good, "reddit": bad},
            provider=provider,
        )
        events = await _collect_events(service)

        failed_events = [e for e in events if isinstance(e, SourceFailed)]
        assert len(failed_events) == 1
        assert failed_events[0].source == "reddit"
        assert "connection refused" in failed_events[0].error

    async def test_all_sources_fail_still_completes(self):
        """All sources fail, pipeline yields SourceFailed events and still completes."""
        bad1 = FailingSource("hackernews", error_msg="timeout")
        bad2 = FailingSource("reddit", error_msg="forbidden")
        provider = MockProvider()

        service = IdeaGenService(
            sources={"hackernews": bad1, "reddit": bad2},
            provider=provider,
        )
        events = await _collect_events(service)

        failed_events = [e for e in events if isinstance(e, SourceFailed)]
        assert len(failed_events) == 2
        source_names = {e.source for e in failed_events}
        assert source_names == {"hackernews", "reddit"}

        # Pipeline should still complete
        complete_events = [e for e in events if isinstance(e, PipelineComplete)]
        assert len(complete_events) == 1

    async def test_partial_failure_continues(self):
        """One source fails, others succeed, pipeline continues with successful data."""
        good = MockSource("hackernews", [_trending_item("Good item")])
        bad = FailingSource("reddit", error_msg="service down")
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(
            sources={"hackernews": good, "reddit": bad},
            provider=provider,
        )
        events = await _collect_events(service)

        # SourceFailed for reddit
        failed_events = [e for e in events if isinstance(e, SourceFailed)]
        assert len(failed_events) == 1
        assert failed_events[0].source == "reddit"

        # Good item still processed
        collect_completed = next(
            e for e in events
            if isinstance(e, StageCompleted) and e.stage == "collect"
        )
        assert collect_completed.metadata["total_items"] == 1

        # Pipeline completed with ideas from the successful source
        assert isinstance(events[-1], PipelineComplete)

    async def test_source_failed_emitted_after_collect_stage_completed(self):
        """SourceFailed events appear after StageCompleted('collect') in the stream."""
        good = MockSource("hackernews", [_trending_item()])
        bad = FailingSource("reddit", error_msg="unavailable")
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(
            sources={"hackernews": good, "reddit": bad},
            provider=provider,
        )
        events = await _collect_events(service)

        collect_completed_idx = next(
            i for i, e in enumerate(events)
            if isinstance(e, StageCompleted) and e.stage == "collect"
        )
        failed_idx = next(
            i for i, e in enumerate(events)
            if isinstance(e, SourceFailed)
        )
        assert failed_idx > collect_completed_idx
