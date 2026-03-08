from __future__ import annotations
import hashlib
import logging
from rapidfuzz import fuzz
from ideagen.core.models import TrendingItem, RunResult

logger = logging.getLogger("ideagen")


def deduplicate(items: list[TrendingItem], threshold: float = 0.85) -> list[TrendingItem]:
    """Remove near-duplicate items using fuzzy title matching.

    Keeps the item with the highest score when duplicates are found.
    This is local string matching only — no LLM calls.
    """
    if not items:
        return []

    unique: list[TrendingItem] = []
    for item in items:
        is_dup = False
        for i, existing in enumerate(unique):
            similarity = fuzz.ratio(item.title.lower(), existing.title.lower()) / 100.0
            if similarity >= threshold:
                is_dup = True
                # Keep the one with higher score
                if item.score > existing.score:
                    unique[i] = item
                logger.debug(
                    f"Dedup: '{item.title}' ~= '{existing.title}' "
                    f"(similarity={similarity:.2f}, keeping higher score)"
                )
                break
        if not is_dup:
            unique.append(item)

    return unique


def content_hash(data: str) -> str:
    """Generate a deterministic content hash for dedup detection."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def idea_content_hash(title: str, problem: str, solution: str) -> str:
    """Generate content hash for an idea."""
    return content_hash(f"{title}|{problem}|{solution}")


def run_content_hash(result: RunResult) -> str:
    """Generate content hash for a run result (for duplicate run detection)."""
    titles = sorted(r.idea.title for r in result.ideas)
    return content_hash("|".join(titles))
