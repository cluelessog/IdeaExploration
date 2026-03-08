from __future__ import annotations
import json
from pathlib import Path
from ideagen.core.models import (
    Domain, TrendingItem, PainPoint, GapAnalysis, Idea, IdeaReport,
)

def _load_template(name: str, override_dir: Path | None = None) -> str | None:
    """Check for user override, return None if not found."""
    if override_dir:
        override_path = override_dir / f"{name}.txt"
        if override_path.exists():
            return override_path.read_text()
    return None


def analyze_trends_prompt(
    items: list[TrendingItem],
    domain: Domain,
    schema: dict,
    override_dir: Path | None = None,
) -> tuple[str | None, str]:
    """Build prompt to extract pain points from trending items."""
    override = _load_template("analyze_trends", override_dir)
    if override:
        return None, override

    items_text = "\n".join(
        f"- [{item.source}] {item.title} (score: {item.score}, comments: {item.comment_count})"
        for item in items
    )

    system = (
        "You are a market analyst identifying pain points and complaints from trending discussions. "
        f"Focus on the {domain.value} domain."
    )

    user = (
        f"Analyze these {len(items)} trending items and extract distinct pain points:\n\n"
        f"{items_text}\n\n"
        f"For each pain point, identify:\n"
        f"- description: Clear description of the problem\n"
        f"- frequency: How often this comes up (rare/occasional/frequent/constant)\n"
        f"- severity: How painful this is (1-10 scale)\n"
        f"- source_items: Which trending items relate to this pain point\n\n"
        f"Return a JSON object with a 'pain_points' array matching this schema:\n"
        f"```json\n{json.dumps(schema, indent=2)}\n```"
    )

    return system, user


def identify_gaps_prompt(
    pain_points: list[PainPoint],
    domain: Domain,
    schema: dict,
    override_dir: Path | None = None,
) -> tuple[str | None, str]:
    """Build prompt to identify market/feature gaps from pain points."""
    override = _load_template("identify_gaps", override_dir)
    if override:
        return None, override

    pains_text = "\n".join(
        f"- {pp.description} (severity: {pp.severity}, frequency: {pp.frequency})"
        for pp in pain_points
    )

    system = (
        "You are a market strategist identifying gaps and opportunities from aggregated pain points. "
        f"Focus on the {domain.value} domain."
    )

    user = (
        f"Given these {len(pain_points)} pain points:\n\n"
        f"{pains_text}\n\n"
        f"Identify market or feature gaps — areas where current solutions are absent or inadequate.\n\n"
        f"Return a JSON object with a 'gaps' array matching this schema:\n"
        f"```json\n{json.dumps(schema, indent=2)}\n```"
    )

    return system, user


def synthesize_ideas_prompt(
    gaps: list[GapAnalysis],
    domain: Domain,
    segment_context: str,
    count: int,
    schema: dict,
    override_dir: Path | None = None,
) -> tuple[str | None, str]:
    """Build prompt to generate novel ideas from gaps and WTP segments."""
    override = _load_template("synthesize_ideas", override_dir)
    if override:
        return None, override

    gaps_text = "\n".join(
        f"- {gap.description} (audience: {gap.affected_audience}, opportunity: {gap.opportunity_size})"
        for gap in gaps
    )

    system = (
        "You are an innovative product strategist generating novel business/product ideas. "
        f"Focus on the {domain.value} domain. Generate ideas that target audiences with high willingness to pay."
    )

    user = (
        f"Given these market gaps:\n\n{gaps_text}\n\n"
    )

    if segment_context:
        user += f"{segment_context}\n\n"

    user += (
        f"Generate exactly {count} novel, actionable business/product ideas.\n"
        f"Each idea should:\n"
        f"- Solve a real problem identified in the gaps\n"
        f"- Target an audience that actually spends money\n"
        f"- Be feasible for a small team to build\n"
        f"- Include an initial novelty score (1-10)\n\n"
        f"Return a JSON object with an 'ideas' array matching this schema:\n"
        f"```json\n{json.dumps(schema, indent=2)}\n```"
    )

    return system, user


def refine_ideas_prompt(
    ideas: list[Idea],
    segment_context: str,
    schema: dict,
    override_dir: Path | None = None,
) -> tuple[str | None, str]:
    """Build prompt for detailed feasibility + market analysis of top ideas."""
    override = _load_template("refine_ideas", override_dir)
    if override:
        return None, override

    ideas_text = "\n".join(
        f"- {idea.title}: {idea.problem_statement} -> {idea.solution} (novelty: {idea.novelty_score})"
        for idea in ideas
    )

    system = (
        "You are a business analyst producing detailed feasibility assessments, "
        "market analyses, and monetization strategies for product ideas."
    )

    user = (
        f"Produce detailed reports for these {len(ideas)} ideas:\n\n{ideas_text}\n\n"
    )

    if segment_context:
        user += f"{segment_context}\n\n"

    user += (
        f"For each idea, provide:\n"
        f"- market_analysis: target audience, market size, competitors, differentiation\n"
        f"- feasibility: complexity (1-10), time to MVP, tech stack, risks\n"
        f"- monetization: revenue model, pricing strategy, revenue potential\n"
        f"- target_segments: which high-WTP segments this serves\n"
        f"- wtp_score: composite WTP attractiveness (0-5)\n\n"
        f"Return a JSON object with an 'reports' array matching this schema:\n"
        f"```json\n{json.dumps(schema, indent=2)}\n```"
    )

    return system, user
