from __future__ import annotations
import json
import logging
from pathlib import Path
from pydantic import BaseModel
from ideagen.core.models import (
    TrendingItem, PainPoint, GapAnalysis, Idea, IdeaReport, Domain,
)
from ideagen.core import prompts
from ideagen.core.wtp_segments import format_segments_for_prompt, get_segments_by_ids, get_top_segments
from ideagen.providers.base import AIProvider

logger = logging.getLogger("ideagen")


class PainPointList(BaseModel):
    pain_points: list[PainPoint]


class GapList(BaseModel):
    gaps: list[GapAnalysis]


class IdeaList(BaseModel):
    ideas: list[Idea]


class IdeaReportList(BaseModel):
    reports: list[IdeaReport]


class AnalysisPipeline:
    """Owns all prompting logic. Uses AIProvider for LLM communication only."""

    def __init__(
        self,
        provider: AIProvider,
        prompt_override_dir: Path | None = None,
    ):
        self._provider = provider
        self._override_dir = prompt_override_dir

    async def analyze(
        self, items: list[TrendingItem], domain: Domain
    ) -> list[PainPoint]:
        """Extract pain points from trending items."""
        schema = PainPointList.model_json_schema()
        system, user = prompts.analyze_trends_prompt(
            items, domain, schema, self._override_dir
        )
        result = await self._provider.complete(user, PainPointList, system)
        return result.pain_points

    async def identify_gaps(
        self, pain_points: list[PainPoint], domain: Domain
    ) -> list[GapAnalysis]:
        """Identify market gaps from pain points."""
        schema = GapList.model_json_schema()
        system, user = prompts.identify_gaps_prompt(
            pain_points, domain, schema, self._override_dir
        )
        result = await self._provider.complete(user, GapList, system)
        return result.gaps

    async def synthesize(
        self,
        gaps: list[GapAnalysis],
        domain: Domain,
        count: int = 10,
        segment_ids: list[str] | None = None,
    ) -> list[Idea]:
        """Generate ideas from gaps targeting WTP segments."""
        if segment_ids:
            segments = get_segments_by_ids(segment_ids)
        else:
            segments = get_top_segments(5)

        segment_context = format_segments_for_prompt(segments)
        schema = IdeaList.model_json_schema()
        system, user = prompts.synthesize_ideas_prompt(
            gaps, domain, segment_context, count, schema, self._override_dir
        )
        result = await self._provider.complete(user, IdeaList, system)
        return result.ideas

    async def refine(
        self,
        ideas: list[Idea],
        segment_ids: list[str] | None = None,
    ) -> list[IdeaReport]:
        """Produce detailed reports for top ideas."""
        if segment_ids:
            segments = get_segments_by_ids(segment_ids)
        else:
            segments = get_top_segments(5)

        segment_context = format_segments_for_prompt(segments)
        schema = IdeaReportList.model_json_schema()
        system, user = prompts.refine_ideas_prompt(
            ideas, segment_context, schema, self._override_dir
        )
        result = await self._provider.complete(user, IdeaReportList, system)
        return result.reports
