from __future__ import annotations
import asyncio
import logging
import time
from collections.abc import AsyncIterator
from ideagen.core.config import IdeaGenConfig
from ideagen.core.models import (
    CancellationToken, Domain, PipelineEvent, PipelineComplete,
    StageStarted, StageCompleted, SourceFailed, IdeaGenerated,
    TrendingItem, RunResult,
)
from ideagen.core.pipeline import AnalysisPipeline
from ideagen.core.dedup import deduplicate, run_content_hash
from ideagen.core.exceptions import IdeaGenError
from ideagen.sources.base import DataSource
from ideagen.providers.base import AIProvider
from ideagen.storage.base import StorageBackend

logger = logging.getLogger("ideagen")


class IdeaGenService:
    """Main orchestrator: collect -> dedup -> analyze -> synthesize -> score -> store."""

    def __init__(
        self,
        sources: dict[str, DataSource],
        provider: AIProvider,
        storage: StorageBackend | None = None,
        config: IdeaGenConfig | None = None,
    ):
        self._sources = sources
        self._provider = provider
        self._storage = storage
        self._config = config or IdeaGenConfig()
        self._pipeline = AnalysisPipeline(
            provider=provider,
            prompt_override_dir=self._config.prompt_override_dir,
        )

    async def run(
        self,
        domain: Domain = Domain.SOFTWARE_SAAS,
        dry_run: bool = False,
        cached: bool = False,
        cancellation_token: CancellationToken | None = None,
        segment_ids: list[str] | None = None,
        idea_count: int | None = None,
    ) -> AsyncIterator[PipelineEvent]:
        """Run the full idea generation pipeline."""
        count = idea_count or self._config.generation.ideas_per_run
        segments = segment_ids or self._config.generation.target_segments or None

        # ---- Stage 1: Collect ----
        if cached and self._storage:
            yield StageStarted(stage="collect", metadata={"mode": "cached"})
            start = time.monotonic()
            # Load from storage — for now yield empty and let storage impl handle
            all_items: list[TrendingItem] = []
            logger.info("Cached mode: skipping collection, loading from storage")
            duration = int((time.monotonic() - start) * 1000)
            yield StageCompleted(stage="collect", duration_ms=duration, metadata={"mode": "cached", "items": 0})
        else:
            yield StageStarted(stage="collect", metadata={"sources": list(self._sources.keys())})
            start = time.monotonic()
            all_items = await self._collect_all(domain)
            duration = int((time.monotonic() - start) * 1000)
            yield StageCompleted(
                stage="collect", duration_ms=duration,
                metadata={"total_items": len(all_items)},
            )

        if cancellation_token and cancellation_token.is_cancelled:
            return

        # ---- Stage 2: Dedup ----
        yield StageStarted(stage="dedup")
        start = time.monotonic()
        threshold = self._config.generation.dedup_threshold
        deduped = deduplicate(all_items, threshold=threshold)
        duration = int((time.monotonic() - start) * 1000)
        yield StageCompleted(
            stage="dedup", duration_ms=duration,
            metadata={"before": len(all_items), "after": len(deduped)},
        )

        if not deduped:
            logger.warning("No trending data found after dedup — aborting pipeline")
            yield PipelineComplete(result=RunResult(
                ideas=[], sources_used=list(self._sources.keys()),
                domain=domain, total_items_scraped=len(all_items),
                total_after_dedup=0,
            ))
            return

        if dry_run:
            logger.info(f"Dry run: {len(deduped)} items would be sent to AI analysis")
            yield PipelineComplete(result=RunResult(
                ideas=[], sources_used=list(self._sources.keys()),
                domain=domain, total_items_scraped=len(all_items),
                total_after_dedup=len(deduped),
            ))
            return

        if cancellation_token and cancellation_token.is_cancelled:
            return

        # ---- Stage 3: Analyze ----
        yield StageStarted(stage="analyze")
        start = time.monotonic()
        pain_points = await self._pipeline.analyze(deduped, domain)
        duration = int((time.monotonic() - start) * 1000)
        yield StageCompleted(
            stage="analyze", duration_ms=duration,
            metadata={"pain_points": len(pain_points)},
        )

        if cancellation_token and cancellation_token.is_cancelled:
            return

        # ---- Stage 4: Identify Gaps ----
        yield StageStarted(stage="identify_gaps")
        start = time.monotonic()
        gaps = await self._pipeline.identify_gaps(pain_points, domain)
        duration = int((time.monotonic() - start) * 1000)
        yield StageCompleted(
            stage="identify_gaps", duration_ms=duration,
            metadata={"gaps": len(gaps)},
        )

        if cancellation_token and cancellation_token.is_cancelled:
            return

        # ---- Stage 5: Synthesize Ideas ----
        yield StageStarted(stage="synthesize")
        start = time.monotonic()
        ideas = await self._pipeline.synthesize(gaps, domain, count=count, segment_ids=segments)
        duration = int((time.monotonic() - start) * 1000)
        yield StageCompleted(
            stage="synthesize", duration_ms=duration,
            metadata={"ideas": len(ideas)},
        )

        for i, idea in enumerate(ideas):
            yield IdeaGenerated(idea=idea, index=i, total=len(ideas))

        if cancellation_token and cancellation_token.is_cancelled:
            return

        # ---- Stage 6: Refine Top Ideas ----
        yield StageStarted(stage="refine")
        start = time.monotonic()
        reports = await self._pipeline.refine(ideas, segment_ids=segments)
        duration = int((time.monotonic() - start) * 1000)
        yield StageCompleted(
            stage="refine", duration_ms=duration,
            metadata={"reports": len(reports)},
        )

        # ---- Build RunResult ----
        result = RunResult(
            ideas=reports,
            sources_used=list(self._sources.keys()),
            domain=domain,
            total_items_scraped=len(all_items),
            total_after_dedup=len(deduped),
            config_snapshot=self._config.model_dump(),
        )
        result.content_hash = run_content_hash(result)

        # ---- Store ----
        if self._storage:
            yield StageStarted(stage="store")
            start = time.monotonic()
            await self._storage.save_run(result)
            duration = int((time.monotonic() - start) * 1000)
            yield StageCompleted(stage="store", duration_ms=duration)

        yield PipelineComplete(result=result)

    async def _collect_all(self, domain: Domain) -> list[TrendingItem]:
        """Collect from all sources in parallel, handling failures gracefully."""
        all_items: list[TrendingItem] = []

        async def collect_one(name: str, source: DataSource) -> tuple[str, list[TrendingItem], str | None]:
            try:
                items = await source.collect(domain)
                return (name, items, None)
            except Exception as e:
                return (name, [], str(e))

        tasks = [collect_one(name, src) for name, src in self._sources.items()]
        results = await asyncio.gather(*tasks)

        for name, items, error in results:
            if error:
                logger.warning(f"Source '{name}' failed: {error}")
            else:
                logger.info(f"Source '{name}' returned {len(items)} items")
                all_items.extend(items)

        return all_items
