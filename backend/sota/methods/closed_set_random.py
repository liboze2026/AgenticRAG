"""Closed-set Random baseline.

Operates within `query.metadata['candidate_docs']`. Returns a deterministic
shuffle based on the query_id. Lower-bound sanity check: a 30-candidate
set should yield Recall@1 ≈ 3.3%, Recall@3 ≈ 10%.
"""
from __future__ import annotations

import logging
import random
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register

logger = logging.getLogger(__name__)


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    candidates = (query.metadata or {}).get("candidate_docs", []) or []
    if not candidates:
        return []
    rng = random.Random(query.query_id)
    shuffled = candidates[:]
    rng.shuffle(shuffled)
    out = [(c, 1, 1.0 - i / max(1, len(shuffled))) for i, c in enumerate(shuffled[:top_k])]
    return out


register(MethodMeta(
    name="closed_set_random",
    version="1.0",
    description="Random ranking within VisDoM per-query candidate_docs (sanity floor).",
    needs=[],
    uses_test_labels=False,
    run=_run,
))
