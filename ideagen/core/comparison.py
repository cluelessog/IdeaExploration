from __future__ import annotations
from pydantic import BaseModel
from rapidfuzz import fuzz


class ComparisonResult(BaseModel):
    added: list[str]       # titles in run_b not matched in run_a
    removed: list[str]     # titles in run_a not matched in run_b
    common: list[tuple[str, str]]  # pairs of matched titles (may differ slightly)
    score_changes: list[dict]  # ideas matched with different WTP scores


def compare_runs(run_a: dict, run_b: dict, threshold: float = 0.85) -> ComparisonResult:
    """Compare two runs and return the diff."""
    titles_a = [r.idea.title for r in run_a.get("ideas", [])]
    titles_b = [r.idea.title for r in run_b.get("ideas", [])]
    scores_a = {r.idea.title: r.wtp_score for r in run_a.get("ideas", [])}
    scores_b = {r.idea.title: r.wtp_score for r in run_b.get("ideas", [])}

    added, removed, common = _match_titles(titles_a, titles_b, threshold)

    score_changes = []
    for ta, tb in common:
        sa = scores_a.get(ta, 0)
        sb = scores_b.get(tb, 0)
        if abs(sa - sb) > 0.1:
            score_changes.append({"title_a": ta, "title_b": tb, "score_a": sa, "score_b": sb})

    return ComparisonResult(added=added, removed=removed, common=common, score_changes=score_changes)


def _match_titles(titles_a: list[str], titles_b: list[str], threshold: float):
    matched_a: set[int] = set()
    matched_b: set[int] = set()
    common: list[tuple[str, str]] = []
    for i, ta in enumerate(titles_a):
        for j, tb in enumerate(titles_b):
            if j in matched_b:
                continue
            if fuzz.ratio(ta.lower(), tb.lower()) / 100.0 >= threshold:
                common.append((ta, tb))
                matched_a.add(i)
                matched_b.add(j)
                break
    removed = [titles_a[i] for i in range(len(titles_a)) if i not in matched_a]
    added = [titles_b[j] for j in range(len(titles_b)) if j not in matched_b]
    return added, removed, common
