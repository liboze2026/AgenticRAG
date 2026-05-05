"""Closed-set BM25-page ⊕ Dense-page hybrid via Reciprocal Rank Fusion.

Standard sparse+dense recipe. Often beats either alone by 3-5 pt R@1 because
sparse and dense capture complementary signal: BM25 nails entity / numeric
matches; dense catches paraphrases and semantic relations.
"""
from __future__ import annotations

import logging
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.baseline_rrf import _rrf_fuse
from backend.sota.methods.closed_set_bm25_page import _run as _bm25_page
from backend.sota.methods.closed_set_dense import _run as _dense

logger = logging.getLogger(__name__)


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    a: List[Tuple[str, int]] = []
    b: List[Tuple[str, int]] = []
    try:
        a = [(d, p) for (d, p, _s) in await _bm25_page(query, top_k * 2, ctx)]
    except Exception as e:
        logger.warning("[hybrid] bm25 leg failed: %s", e)
    try:
        b = [(d, p) for (d, p, _s) in await _dense(query, top_k * 2, ctx)]
    except Exception as e:
        logger.warning("[hybrid] dense leg failed: %s", e)
    return _rrf_fuse([a, b], k=60, top_k=top_k)


register(MethodMeta(
    name="closed_set_hybrid",
    version="1.0",
    description="RRF fusion of BM25-page + Dense (bge-base) — sparse+dense hybrid.",
    needs=["visdom_corpus", "dense_index"],
    uses_test_labels=False,
    run=_run,
))
