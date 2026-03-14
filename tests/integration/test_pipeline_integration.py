"""Integration tests for the full IdeaGenService pipeline.

These tests wire together real service/pipeline logic with mocked external
boundaries (DataSource, AIProvider, StorageBackend) to verify end-to-end
behaviour across the collect -> dedup -> analyze -> identify_gaps ->
synthesize -> refine -> store pipeline.
"""
from __future__ import annotations

from datetime import datetime
from typing import TypeVar

from pydantic import BaseModel

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
# Mock implementations (adapted from tests/core/test_service.py)
# ---------------------------------------------------------------------------

class MockSource(DataSource):
    """DataSource that returns pre-configured items or raises on demand."""

    def __init__(
        self,
        name_: str,
        items: list[TrendingItem] | None = None,
        fail: bool = False,
    ):
        self._name = name_
        self._items = items or []
        self._fail = fail
        self.collect_call_count = 0

    @property
    def name(self) -> str:
        return self._name

    async def collect(self, domain: Domain, limit: int = 50) -> list[TrendingItem]:
        self.collect_call_count += 1
        if self._fail:
            raise RuntimeError(f"Source {self._name} is unavailable")
        return self._items

    async def is_available(self) -> bool:
        return not self._fail


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
        self.calls.append(
            {
                "user_prompt": user_prompt,
                "response_type": response_type,
                "system_prompt": system_prompt,
            }
        )
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

    async def search_ideas(
        self, query: str, offset: int = 0, limit: int = 50
    ) -> list[IdeaReport]:
        return []

    async def get_run_detail(self, run_id_prefix: str) -> dict | None:
        return None

    async def save_scrape_cache(self, batch_id: str, source: str, items: list) -> None:
        pass

    async def load_latest_scrape_cache(self) -> list:
        return []


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------

def _item(title: str = "Fast SaaS Tool", score: int = 100, source: str = "hackernews") -> TrendingItem:
    return TrendingItem(
        title=title,
        url="https://example.com",
        score=score,
        source=source,
        timestamp=datetime(2024, 6, 1),
        comment_count=20,
    )


def _pain_point(desc: str = "Too slow") -> PainPoint:
    return PainPoint(description=desc, frequency="frequent", severity=7.5)


def _gap(desc: str = "No fast solution exists") -> GapAnalysis:
    return GapAnalysis(
        description=desc,
        evidence=["evidence A", "evidence B"],
        affected_audience="indie developers",
        opportunity_size="large",
    )


def _idea(title: str = "VelocityApp") -> Idea:
    return Idea(
        title=title,
        problem_statement="Workflows are sluggish",
        solution="Async-first pipeline engine",
        domain=Domain.SOFTWARE_SAAS,
        novelty_score=8.5,
    )


def _idea_report(title: str = "VelocityApp") -> IdeaReport:
    return IdeaReport(
        idea=_idea(title),
        market_analysis=MarketAnalysis(
            target_audience="developer teams",
            market_size_estimate="$2B",
            competitors=["CompA", "CompB"],
            differentiation="10x faster with zero config",
        ),
        feasibility=FeasibilityScore(
            complexity=4,
            time_to_mvp="2 months",
            suggested_tech_stack=["Python", "asyncio", "FastAPI"],
            risks=["low initial awareness"],
        ),
        monetization=MonetizationAngle(
            revenue_model="SaaS subscription",
            pricing_strategy="$49/mo",
            estimated_revenue_potential="$1M ARR",
        ),
        target_segments=[],
        wtp_score=4.2,
    )


def _queue_full_pipeline(provider: MockProvider, idea_titles: list[str] | None = None) -> None:
    """Queue the four LLM responses required for a complete pipeline run."""
    titles = idea_titles or ["VelocityApp"]
    provider.queue(PainPointList(pain_points=[_pain_point()]))
    provider.queue(GapList(gaps=[_gap()]))
    provider.queue(IdeaList(ideas=[_idea(t) for t in titles]))
    provider.queue(IdeaReportList(reports=[_idea_report(t) for t in titles]))


async def _run(service: IdeaGenService, **kwargs) -> list[PipelineEvent]:
    """Drain the service's async generator into a list."""
    events: list[PipelineEvent] = []
    async for event in service.run(**kwargs):
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Test 1: Full pipeline with mocked externals produces valid RunResult
# ---------------------------------------------------------------------------

class TestFullPipelineRunResult:
    """Verify that the complete pipeline wires all stages and returns a valid RunResult."""

    async def test_run_result_has_ideas(self):
        source = MockSource("hackernews", [_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider, idea_titles=["VelocityApp", "DataSync"])

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _run(service)

        complete = next(e for e in events if isinstance(e, PipelineComplete))
        assert len(complete.result.ideas) == 2

    async def test_run_result_has_correct_domain(self):
        source = MockSource("hackernews", [_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _run(service, domain=Domain.BROAD_BUSINESS)

        complete = next(e for e in events if isinstance(e, PipelineComplete))
        assert complete.result.domain == Domain.BROAD_BUSINESS

    async def test_run_result_sources_used(self):
        source = MockSource("hackernews", [_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(
            sources={"hackernews": source, "producthunt": MockSource("producthunt", [_item("PH item", source="producthunt")])},
            provider=provider,
        )
        events = await _run(service)

        complete = next(e for e in events if isinstance(e, PipelineComplete))
        assert set(complete.result.sources_used) == {"hackernews", "producthunt"}

    async def test_run_result_has_timestamps(self):
        source = MockSource("hackernews", [_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _run(service)

        complete = next(e for e in events if isinstance(e, PipelineComplete))
        assert complete.result.timestamp is not None
        assert isinstance(complete.result.timestamp, datetime)

    async def test_run_result_has_content_hash(self):
        source = MockSource("hackernews", [_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _run(service)

        complete = next(e for e in events if isinstance(e, PipelineComplete))
        assert complete.result.content_hash != ""

    async def test_run_result_scrape_counts(self):
        items = [_item(f"Item {i}") for i in range(3)]
        source = MockSource("hackernews", items)
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _run(service)

        complete = next(e for e in events if isinstance(e, PipelineComplete))
        assert complete.result.total_items_scraped == 3
        assert complete.result.total_after_dedup == 3

    async def test_four_llm_calls_made_in_correct_order(self):
        """Pipeline must call provider exactly 4 times: analyze, gaps, synthesize, refine."""
        source = MockSource("hackernews", [_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        await _run(service)

        assert len(provider.calls) == 4
        assert provider.calls[0]["response_type"] is PainPointList
        assert provider.calls[1]["response_type"] is GapList
        assert provider.calls[2]["response_type"] is IdeaList
        assert provider.calls[3]["response_type"] is IdeaReportList

    async def test_pipeline_complete_is_last_event(self):
        source = MockSource("hackernews", [_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _run(service)

        assert isinstance(events[-1], PipelineComplete)

    async def test_all_six_stages_emitted(self):
        source = MockSource("hackernews", [_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _run(service)

        started = {e.stage for e in events if isinstance(e, StageStarted)}
        completed = {e.stage for e in events if isinstance(e, StageCompleted)}
        expected = {"collect", "dedup", "analyze", "identify_gaps", "synthesize", "refine"}
        assert expected.issubset(started)
        assert expected.issubset(completed)

    async def test_idea_generated_events_carry_correct_indices(self):
        source = MockSource("hackernews", [_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider, idea_titles=["AppA", "AppB", "AppC"])

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _run(service)

        idea_events = [e for e in events if isinstance(e, IdeaGenerated)]
        assert len(idea_events) == 3
        assert [e.index for e in idea_events] == [0, 1, 2]
        assert all(e.total == 3 for e in idea_events)

    async def test_with_storage_saves_run_and_emits_store_stage(self):
        source = MockSource("hackernews", [_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)
        storage = MockStorage()

        service = IdeaGenService(
            sources={"hackernews": source},
            provider=provider,
            storage=storage,
        )
        events = await _run(service)

        assert len(storage.saved) == 1
        started_stages = {e.stage for e in events if isinstance(e, StageStarted)}
        assert "store" in started_stages

    async def test_dedup_reduces_near_duplicate_items(self):
        """Near-duplicate titles should be collapsed before the LLM sees them."""
        items = [
            _item("Fast SaaS Pipeline Tool", score=200),
            _item("Fast SaaS Pipeline Tool", score=100),  # exact dup
        ]
        source = MockSource("hackernews", items)
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _run(service)

        dedup_completed = next(
            e for e in events if isinstance(e, StageCompleted) and e.stage == "dedup"
        )
        assert dedup_completed.metadata["before"] == 2
        assert dedup_completed.metadata["after"] == 1


# ---------------------------------------------------------------------------
# Test 2: Cancellation mid-pipeline stops execution
# ---------------------------------------------------------------------------

class TestCancellationMidPipeline:
    """Cancelling after collect completes must stop the pipeline before any LLM calls."""

    async def test_cancel_before_run_stops_after_collect_stage(self):
        """Token cancelled before run() is called — pipeline exits after collect/dedup."""
        source = MockSource("hackernews", [_item()])
        provider = MockProvider()

        token = CancellationToken()
        token.cancel()

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _run(service, cancellation_token=token)

        started_stages = {e.stage for e in events if isinstance(e, StageStarted)}
        # collect starts (and completes) before the first cancellation check
        assert "collect" in started_stages
        # analyze must NOT start — it comes after the first check
        assert "analyze" not in started_stages

    async def test_cancel_before_run_produces_no_llm_calls(self):
        source = MockSource("hackernews", [_item()])
        provider = MockProvider()

        token = CancellationToken()
        token.cancel()

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        await _run(service, cancellation_token=token)

        assert provider.calls == []

    async def test_cancel_before_run_emits_no_pipeline_complete(self):
        source = MockSource("hackernews", [_item()])
        provider = MockProvider()

        token = CancellationToken()
        token.cancel()

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _run(service, cancellation_token=token)

        complete_events = [e for e in events if isinstance(e, PipelineComplete)]
        assert complete_events == []

    async def test_cancel_during_collect_stops_before_analyze(self):
        """Token cancelled concurrently while collect is running."""
        token = CancellationToken()

        class SlowSource(DataSource):
            @property
            def name(self) -> str:
                return "slow"

            async def collect(self, domain: Domain, limit: int = 50) -> list[TrendingItem]:
                # Cancel during collection — pipeline should still check after collect completes
                token.cancel()
                return [_item()]

            async def is_available(self) -> bool:
                return True

        provider = MockProvider()
        service = IdeaGenService(sources={"slow": SlowSource()}, provider=provider)
        events = await _run(service, cancellation_token=token)

        # After collect, the token is cancelled; the pipeline must not proceed to analyze
        assert provider.calls == []
        complete_events = [e for e in events if isinstance(e, PipelineComplete)]
        assert complete_events == []

    async def test_uncancelled_token_allows_full_pipeline(self):
        """A token that is never cancelled must not interfere with normal execution."""
        source = MockSource("hackernews", [_item()])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        token = CancellationToken()  # never cancelled

        service = IdeaGenService(sources={"hackernews": source}, provider=provider)
        events = await _run(service, cancellation_token=token)

        assert isinstance(events[-1], PipelineComplete)
        assert len(provider.calls) == 4

    async def test_cancel_after_analyze_stops_before_synthesize(self):
        """Token cancelled during the analyze stage (after first LLM call completes)."""
        token = CancellationToken()

        class CancellingProvider(AIProvider):
            """Cancels the token after the first complete() call (analyze stage)."""

            def __init__(self):
                self.calls: list[dict] = []
                self._inner = MockProvider()
                # Pre-queue responses for all stages so indexing is straightforward
                self._inner.queue(PainPointList(pain_points=[_pain_point()]))
                self._inner.queue(GapList(gaps=[_gap()]))
                self._inner.queue(IdeaList(ideas=[_idea()]))
                self._inner.queue(IdeaReportList(reports=[_idea_report()]))

            async def complete(
                self,
                user_prompt: str,
                response_type: type[T],
                system_prompt: str | None = None,
            ) -> T:
                result = await self._inner.complete(user_prompt, response_type, system_prompt)
                self.calls.append({"response_type": response_type})
                # After analyze completes, cancel so identify_gaps is blocked
                if response_type is PainPointList:
                    token.cancel()
                return result

        cp = CancellingProvider()
        source = MockSource("hackernews", [_item()])
        service = IdeaGenService(sources={"hackernews": source}, provider=cp)
        events = await _run(service, cancellation_token=token)

        # Only one LLM call (analyze) should have been made
        assert len(cp.calls) == 1
        assert cp.calls[0]["response_type"] is PainPointList

        # Pipeline should not have reached synthesize or refine
        started_stages = {e.stage for e in events if isinstance(e, StageStarted)}
        assert "synthesize" not in started_stages
        assert "refine" not in started_stages

        # No PipelineComplete event
        assert not any(isinstance(e, PipelineComplete) for e in events)


# ---------------------------------------------------------------------------
# Test 3: Partial source failure + pipeline continuation
# ---------------------------------------------------------------------------

class TestPartialSourceFailure:
    """One failing source must not abort the pipeline; successful source data is used."""

    async def test_pipeline_completes_when_one_source_fails(self):
        good = MockSource("hackernews", [_item("Good item")])
        bad = MockSource("reddit", fail=True)
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(
            sources={"hackernews": good, "reddit": bad},
            provider=provider,
        )
        events = await _run(service)

        assert isinstance(events[-1], PipelineComplete)

    async def test_only_good_source_items_used(self):
        good = MockSource("hackernews", [_item("Valid item")])
        bad = MockSource("reddit", fail=True)
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(
            sources={"hackernews": good, "reddit": bad},
            provider=provider,
        )
        events = await _run(service)

        collect_done = next(
            e for e in events if isinstance(e, StageCompleted) and e.stage == "collect"
        )
        # Only the one item from the good source should be present
        assert collect_done.metadata["total_items"] == 1

    async def test_no_source_failed_event_emitted(self):
        """Service logs a warning but does NOT emit a SourceFailed pipeline event."""
        good = MockSource("hackernews", [_item()])
        bad = MockSource("reddit", fail=True)
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(
            sources={"hackernews": good, "reddit": bad},
            provider=provider,
        )
        events = await _run(service)

        source_failed_events = [e for e in events if isinstance(e, SourceFailed)]
        assert source_failed_events == []

    async def test_pipeline_complete_event_still_emitted(self):
        good = MockSource("hackernews", [_item()])
        bad = MockSource("reddit", fail=True)
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(
            sources={"hackernews": good, "reddit": bad},
            provider=provider,
        )
        events = await _run(service)

        complete_events = [e for e in events if isinstance(e, PipelineComplete)]
        assert len(complete_events) == 1

    async def test_result_lists_both_source_names_regardless_of_failure(self):
        """sources_used always reflects the configured sources, not just successful ones."""
        good = MockSource("hackernews", [_item()])
        bad = MockSource("reddit", fail=True)
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(
            sources={"hackernews": good, "reddit": bad},
            provider=provider,
        )
        events = await _run(service)

        complete = next(e for e in events if isinstance(e, PipelineComplete))
        assert "hackernews" in complete.result.sources_used
        assert "reddit" in complete.result.sources_used

    async def test_all_sources_fail_yields_empty_result(self):
        bad1 = MockSource("hackernews", fail=True)
        bad2 = MockSource("reddit", fail=True)
        provider = MockProvider()

        service = IdeaGenService(
            sources={"hackernews": bad1, "reddit": bad2},
            provider=provider,
        )
        events = await _run(service)

        complete = next(e for e in events if isinstance(e, PipelineComplete))
        assert complete.result.ideas == []
        assert complete.result.total_after_dedup == 0
        # No LLM calls should occur when there are no items
        assert provider.calls == []

    async def test_multiple_good_sources_items_are_combined(self):
        src_a = MockSource("hackernews", [_item("HN item 1"), _item("HN item 2")])
        src_b = MockSource("producthunt", [_item("PH item 1", source="producthunt")])
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(
            sources={"hackernews": src_a, "producthunt": src_b},
            provider=provider,
        )
        events = await _run(service)

        collect_done = next(
            e for e in events if isinstance(e, StageCompleted) and e.stage == "collect"
        )
        assert collect_done.metadata["total_items"] == 3

    async def test_good_source_collect_called_once_even_when_peer_fails(self):
        good = MockSource("hackernews", [_item()])
        bad = MockSource("reddit", fail=True)
        provider = MockProvider()
        _queue_full_pipeline(provider)

        service = IdeaGenService(
            sources={"hackernews": good, "reddit": bad},
            provider=provider,
        )
        await _run(service)

        assert good.collect_call_count == 1
