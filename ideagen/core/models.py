from __future__ import annotations

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Domain enum
# ---------------------------------------------------------------------------

class Domain(str, Enum):
    SOFTWARE_SAAS = "SOFTWARE_SAAS"
    BROAD_BUSINESS = "BROAD_BUSINESS"
    CONTENT_MEDIA = "CONTENT_MEDIA"


# ---------------------------------------------------------------------------
# WTP (Willingness-To-Pay) models
# ---------------------------------------------------------------------------

class WTPSegment(BaseModel):
    id: str
    name: str
    emotional_driver: str
    spending_areas: list[str]
    pain_tolerance: float  # 1-5 scale
    wtp_score: float  # weighted composite


class WTPScoringCriteria(BaseModel):
    emotional_intensity: float = 0.25
    pain_frequency: float = 0.20
    price_insensitivity: float = 0.20
    market_size: float = 0.15
    accessibility: float = 0.10
    defensibility: float = 0.10


# ---------------------------------------------------------------------------
# Trending / scraping primitives
# ---------------------------------------------------------------------------

class TrendingItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    url: str
    score: int = 0
    source: str
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    comment_count: int = 0


# ---------------------------------------------------------------------------
# Analysis models
# ---------------------------------------------------------------------------

class PainPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    description: str
    frequency: str
    severity: float  # 1-10
    source_items: list[str] = Field(default_factory=list)


class GapAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    description: str
    evidence: list[str]
    affected_audience: str
    opportunity_size: str = "unknown"


# ---------------------------------------------------------------------------
# Core idea model
# ---------------------------------------------------------------------------

class Idea(BaseModel):
    title: str
    problem_statement: str
    solution: str
    domain: Domain
    novelty_score: float  # 1-10
    content_hash: str = ""  # for dedup detection
    tags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Report sub-models
# ---------------------------------------------------------------------------

class MarketAnalysis(BaseModel):
    target_audience: str
    market_size_estimate: str
    competitors: list[str] = Field(default_factory=list)
    differentiation: str


class FeasibilityScore(BaseModel):
    complexity: int  # 1-10
    time_to_mvp: str
    suggested_tech_stack: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class MonetizationAngle(BaseModel):
    revenue_model: str
    pricing_strategy: str
    estimated_revenue_potential: str


# ---------------------------------------------------------------------------
# Composite report models
# ---------------------------------------------------------------------------

class IdeaReport(BaseModel):
    idea: Idea
    market_analysis: MarketAnalysis
    feasibility: FeasibilityScore
    monetization: MonetizationAngle
    target_segments: list[WTPSegment] = Field(default_factory=list)
    wtp_score: float = 0.0
    generated_at: datetime = Field(default_factory=datetime.now)


class RunResult(BaseModel):
    ideas: list[IdeaReport]
    sources_used: list[str]
    domain: Domain
    timestamp: datetime = Field(default_factory=datetime.now)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    content_hash: str = ""
    total_items_scraped: int = 0
    total_after_dedup: int = 0


# ---------------------------------------------------------------------------
# Pipeline event hierarchy
# ---------------------------------------------------------------------------

class PipelineEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: str
    timestamp: datetime = Field(default_factory=datetime.now)


class StageStarted(PipelineEvent):
    stage: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    event_type: str = "stage_started"


class StageCompleted(PipelineEvent):
    stage: str
    duration_ms: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    event_type: str = "stage_completed"


class SourceFailed(PipelineEvent):
    source: str
    error: str
    event_type: str = "source_failed"


class IdeaGenerated(PipelineEvent):
    idea: Idea
    index: int
    total: int
    event_type: str = "idea_generated"


class PipelineComplete(PipelineEvent):
    result: RunResult
    event_type: str = "pipeline_complete"


# ---------------------------------------------------------------------------
# Cancellation token (plain class, not Pydantic)
# ---------------------------------------------------------------------------

class CancellationToken:
    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self, timeout: float | None = None) -> bool:
        """Return True if cancelled within timeout, False if timeout elapsed first."""
        if timeout is None:
            await self._event.wait()
            return True
        try:
            await asyncio.wait_for(asyncio.shield(self._event.wait()), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
