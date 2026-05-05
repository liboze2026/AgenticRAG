"""Page-level retrieval evaluation: Recall@1, Recall@3, MRR, Hit@1.

Strict containment: a hit means (doc_id, page_number) appears in gold set.
Bootstrap CI is non-parametric — works for binary (Recall) and continuous (RR).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

PageKey = Tuple[str, int]


@dataclass
class PerQueryResult:
    query_id: str
    hit_at_1: float
    hit_at_3: float
    rr: float
    latency_ms: int
    error: Optional[str] = None


def score_query(gold_pages: List[PageKey], ranked_pages: List[PageKey]) -> PerQueryResult:
    """Return per-query metrics. RR = 1/(rank of first gold), 0 if absent."""
    gold = set(gold_pages)
    if not gold or not ranked_pages:
        return PerQueryResult(query_id="", hit_at_1=0.0, hit_at_3=0.0, rr=0.0, latency_ms=0)

    rr = 0.0
    for i, key in enumerate(ranked_pages):
        if key in gold:
            rr = 1.0 / (i + 1)
            break
    top1 = ranked_pages[:1]
    top3 = ranked_pages[:3]
    hit1 = 1.0 if any(k in gold for k in top1) else 0.0
    hit3 = 1.0 if any(k in gold for k in top3) else 0.0
    return PerQueryResult(query_id="", hit_at_1=hit1, hit_at_3=hit3, rr=rr, latency_ms=0)


def aggregate_metrics(results: List[PerQueryResult]) -> Dict[str, float]:
    n = len(results)
    if n == 0:
        return {"recall@1": 0.0, "recall@3": 0.0, "mrr": 0.0, "hit@1": 0.0, "n": 0}
    return {
        "recall@1": sum(r.hit_at_1 for r in results) / n,
        "recall@3": sum(r.hit_at_3 for r in results) / n,
        "mrr": sum(r.rr for r in results) / n,
        "hit@1": sum(r.hit_at_1 for r in results) / n,
        "n": n,
    }


def bootstrap_ci(
    values: List[float], n_resamples: int = 1000, alpha: float = 0.05, seed: int = 0,
) -> Tuple[float, float]:
    """95% percentile bootstrap CI for the mean. Non-parametric, no scipy."""
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo_idx = max(0, int((alpha / 2) * n_resamples))
    hi_idx = min(n_resamples - 1, int((1 - alpha / 2) * n_resamples))
    return means[lo_idx], means[hi_idx]
