"""Built-in WTP (Willingness-to-Pay) knowledge base.

22 high willingness-to-pay audience segments with scoring framework,
emotional drivers, spending areas, and pain tolerance ratings.

Source: .omc/research/high-wtp-segments.md
"""

from __future__ import annotations

from ideagen.core.models import WTPSegment, WTPScoringCriteria

DEFAULT_SCORING = WTPScoringCriteria()

WTP_SEGMENTS: dict[str, WTPSegment] = {
    "parents": WTPSegment(
        id="parents",
        name="Parents of Young Children (Ages 0-12)",
        emotional_driver="Fear of falling behind, guilt about not providing enough, desire to give children every advantage",
        spending_areas=[
            "education", "tutoring", "apps", "safety", "health",
            "childcare", "enrichment activities", "screen time management",
        ],
        pain_tolerance=5.0,
        wtp_score=4.65,
    ),
    "pet_owners": WTPSegment(
        id="pet_owners",
        name="Pet Owners (Pet Parents)",
        emotional_driver="Pets as family members, emotional bond, guilt about leaving pets alone, aging pet concerns",
        spending_areas=[
            "premium food", "veterinary care", "pet insurance", "grooming",
            "boarding", "pet tech", "GPS trackers", "accessories",
        ],
        pain_tolerance=4.0,
        wtp_score=4.10,
    ),
    "chronic_health": WTPSegment(
        id="chronic_health",
        name="People with Chronic Health Conditions",
        emotional_driver="Desperation for relief, fear of deterioration, desire for normalcy",
        spending_areas=[
            "supplements", "alternative therapies", "health tracking",
            "specialized diets", "mental health", "telehealth", "coaching",
        ],
        pain_tolerance=5.0,
        wtp_score=4.60,
    ),
    "small_business": WTPSegment(
        id="small_business",
        name="Small Business Owners & Solopreneurs",
        emotional_driver="Time scarcity, fear of failure, compliance anxiety, desire to appear professional",
        spending_areas=[
            "accounting", "marketing", "legal templates", "scheduling",
            "CRM", "website builders", "AI assistants", "business formation",
        ],
        pain_tolerance=4.0,
        wtp_score=4.30,
    ),
    "brides_grooms": WTPSegment(
        id="brides_grooms",
        name="Brides & Grooms (Wedding Planning)",
        emotional_driver="Once-in-a-lifetime psychology, social pressure, fear of regret, desire for perfection",
        spending_areas=[
            "venue", "photography", "planning tools", "catering",
            "invitations", "coordination", "honeymoon planning",
        ],
        pain_tolerance=5.0,
        wtp_score=4.20,
    ),
    "hobbyists": WTPSegment(
        id="hobbyists",
        name="Hobbyist Enthusiasts",
        emotional_driver="Identity expression, community belonging, pursuit of mastery, gear acquisition",
        spending_areas=[
            "equipment", "courses", "community memberships", "software tools",
            "materials", "event tickets", "storage",
        ],
        pain_tolerance=4.0,
        wtp_score=4.00,
    ),
    "remote_workers": WTPSegment(
        id="remote_workers",
        name="Remote Workers & Digital Nomads",
        emotional_driver="Productivity impacts income, lifestyle optimization, loneliness drives tool adoption",
        spending_areas=[
            "coworking", "productivity software", "VPN", "ergonomic equipment",
            "travel logistics", "health insurance", "community platforms",
        ],
        pain_tolerance=3.5,
        wtp_score=3.70,
    ),
    "fitness": WTPSegment(
        id="fitness",
        name="Fitness & Body Transformation Seekers",
        emotional_driver="Deep identity and self-worth connection, social media pressure, addictive feedback loops",
        spending_areas=[
            "gym memberships", "personal training", "supplements", "meal plans",
            "fitness apps", "wearables", "recovery tools", "coaching",
        ],
        pain_tolerance=4.5,
        wtp_score=4.50,
    ),
    "creators": WTPSegment(
        id="creators",
        name="Aspiring Creators & Influencers",
        emotional_driver="Dream of independence, invest-in-yourself narrative, fear of being left behind",
        spending_areas=[
            "courses", "editing software", "equipment", "growth tools",
            "analytics", "scheduling", "branding", "legal",
        ],
        pain_tolerance=4.0,
        wtp_score=4.00,
    ),
    "homeowners": WTPSegment(
        id="homeowners",
        name="Homeowners (New & Renovation-Focused)",
        emotional_driver="Largest financial asset protection, nesting instinct, social comparison",
        spending_areas=[
            "renovation planning", "smart home tech", "interior design",
            "maintenance", "security systems", "energy efficiency", "landscaping",
        ],
        pain_tolerance=4.0,
        wtp_score=4.10,
    ),
    "elder_care": WTPSegment(
        id="elder_care",
        name="Aging Adults & Their Adult Children (Elder Care)",
        emotional_driver="Fear of parent's decline, guilt about not being present, desperation for reliable care",
        spending_areas=[
            "home care", "medical alerts", "care coordination",
            "medication management", "facility research", "legal planning",
            "cognitive health",
        ],
        pain_tolerance=5.0,
        wtp_score=4.60,
    ),
    "life_transitions": WTPSegment(
        id="life_transitions",
        name="People Going Through Major Life Transitions",
        emotional_driver="Urgency, confusion, emotional vulnerability during divorce, job loss, relocation, grief",
        spending_areas=[
            "legal services", "therapy", "financial planning", "moving",
            "job search", "dating", "skill acquisition", "support communities",
        ],
        pain_tolerance=4.5,
        wtp_score=4.00,
    ),
    "career_seekers": WTPSegment(
        id="career_seekers",
        name="Professionals Seeking Career Advancement",
        emotional_driver="Career tied to identity and income, fear of stagnation, competition anxiety",
        spending_areas=[
            "certifications", "online courses", "executive coaching",
            "resume optimization", "networking tools", "interview prep",
            "personal branding",
        ],
        pain_tolerance=4.0,
        wtp_score=4.10,
    ),
    "anxious_safety": WTPSegment(
        id="anxious_safety",
        name="Anxious/Safety-Conscious Individuals",
        emotional_driver="Fear as spending motivator, personal safety, cybersecurity, financial security anxiety",
        spending_areas=[
            "home security", "identity theft protection", "VPNs",
            "insurance", "health screening", "emergency prep", "cybersecurity",
        ],
        pain_tolerance=4.0,
        wtp_score=3.90,
    ),
    "luxury_status": WTPSegment(
        id="luxury_status",
        name="Luxury & Status Seekers",
        emotional_driver="Social signaling, self-reward, aspiration — spending IS the point",
        spending_areas=[
            "fashion", "watches", "cars", "travel", "dining",
            "memberships", "exclusive experiences", "concierge services",
        ],
        pain_tolerance=5.0,
        wtp_score=3.80,
    ),
    "neurodivergent": WTPSegment(
        id="neurodivergent",
        name="Neurodivergent Adults (ADHD, Autism, etc.)",
        emotional_driver="Mainstream tools don't work, desperate for brain-compatible solutions, years of failed approaches",
        spending_areas=[
            "ADHD productivity tools", "coaching", "therapy",
            "medication management", "sensory tools", "planners",
            "body-doubling services", "community",
        ],
        pain_tolerance=4.0,
        wtp_score=4.05,
    ),
    "investors": WTPSegment(
        id="investors",
        name="Investors & Traders (Retail)",
        emotional_driver="Greed and fear, desire for edge, FOMO, dream of financial freedom",
        spending_areas=[
            "trading platforms", "market data", "analysis tools", "courses",
            "newsletters", "alerts", "portfolio trackers", "tax optimization",
        ],
        pain_tolerance=4.5,
        wtp_score=4.10,
    ),
    "immigrants": WTPSegment(
        id="immigrants",
        name="Immigrants & Expats",
        emotional_driver="Navigating foreign systems with high stakes, language barriers amplify WTP",
        spending_areas=[
            "immigration legal", "language learning", "credential recognition",
            "money transfer", "cultural integration", "tax compliance",
            "housing search",
        ],
        pain_tolerance=4.0,
        wtp_score=3.80,
    ),
    "fertility": WTPSegment(
        id="fertility",
        name="People with Fertility/Family Planning Challenges",
        emotional_driver="Deeply emotional, biological clock urgency, failure feels devastating, social pressure",
        spending_areas=[
            "IVF", "fertility tracking", "supplements", "coaching",
            "mental health", "adoption services", "surrogacy", "egg/sperm banking",
        ],
        pain_tolerance=5.0,
        wtp_score=4.40,
    ),
    "students": WTPSegment(
        id="students",
        name="Students & Exam Preppers (High-Stakes Testing)",
        emotional_driver="Career-defining outcomes, failure means delayed career and social shame",
        spending_areas=[
            "prep courses", "tutoring", "practice tests", "study tools",
            "productivity apps", "anxiety management", "study communities",
        ],
        pain_tolerance=4.0,
        wtp_score=3.90,
    ),
    "legal": WTPSegment(
        id="legal",
        name="People Managing Legal Situations",
        emotional_driver="Asymmetric consequences (jail, financial ruin), complexity creates helplessness, urgency",
        spending_areas=[
            "legal representation", "document prep", "legal research",
            "compliance software", "contract review", "mediation",
            "court preparation",
        ],
        pain_tolerance=5.0,
        wtp_score=4.20,
    ),
    "knowledge_workers": WTPSegment(
        id="knowledge_workers",
        name="Content Creators & Knowledge Workers",
        emotional_driver="Information overload, inability to organize and act on information costs real money",
        spending_areas=[
            "note-taking", "AI assistants", "research tools",
            "writing assistants", "summarization", "knowledge base software",
            "curation tools",
        ],
        pain_tolerance=3.5,
        wtp_score=3.60,
    ),
}


def get_segment(segment_id: str) -> WTPSegment | None:
    """Get a WTP segment by its ID."""
    return WTP_SEGMENTS.get(segment_id)


def get_segments_by_ids(segment_ids: list[str]) -> list[WTPSegment]:
    """Get multiple WTP segments by their IDs. Skips unknown IDs."""
    return [s for sid in segment_ids if (s := WTP_SEGMENTS.get(sid))]


def get_top_segments(n: int = 5) -> list[WTPSegment]:
    """Get top N segments by WTP score."""
    return sorted(WTP_SEGMENTS.values(), key=lambda s: s.wtp_score, reverse=True)[:n]


def get_all_segment_ids() -> list[str]:
    """Get all available segment IDs."""
    return list(WTP_SEGMENTS.keys())


def format_segments_for_prompt(segments: list[WTPSegment]) -> str:
    """Format WTP segments as context for LLM prompts."""
    lines = ["## Target Audience Segments (High Willingness-to-Pay)\n"]
    for seg in segments:
        lines.append(f"### {seg.name} (WTP Score: {seg.wtp_score}/5.0)")
        lines.append(f"- **Emotional Driver:** {seg.emotional_driver}")
        lines.append(f"- **Key Spending Areas:** {', '.join(seg.spending_areas)}")
        lines.append(f"- **Pain Tolerance:** {seg.pain_tolerance}/5.0")
        lines.append("")
    return "\n".join(lines)
