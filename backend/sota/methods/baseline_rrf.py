"""RRF baseline: BM25 ⊕ ColPali via Reciprocal Rank Fusion."""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.baseline_bm25 import _run as _bm25_run
from backend.sota.methods.baseline_colpali import _run as _colpali_run

logger = logging.getLogger(__name__)


def _rrf_fuse(
    ranked_lists: List[List[Tuple[str, int]]], k: int = 60, top_k: int = 10,
) -> List[Tuple[str, int, float]]:
    scores: Dict[Tuple[str, int], float] = {}
    for ranked in ranked_lists:
        for i, key in enumerate(ranked):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + i + 1)
    fused = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    return [(d, p, s) for ((d, p), s) in fused]


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    a: List[Tuple[str, int]] = []
    b: List[Tuple[str, int]] = []
    try:
        a = [(d, p) for (d, p, _s) in await _colpali_run(query, top_k * 2, ctx)]
    except Exception as e:
        logger.warning("[rrf] ColPali leg failed: %s", e)
    try:
        b = [(d, p) for (d, p, _s) in await _bm25_run(query, top_k * 2, ctx)]
    except Exception as e:
        logger.warning("[rrf] BM25 leg failed: %s", e)
    return _rrf_fuse([a, b], k=60, top_k=top_k)


register(MethodMeta(
    name="baseline_rrf",
    version="1.0",
    description="Reciprocal Rank Fusion of ColPali + BM25 (k=60).",
    needs=["pipeline", "lab_bundle.hybrid"],
    uses_test_labels=False,
    run=_run,
))
