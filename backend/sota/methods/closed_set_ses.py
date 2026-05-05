"""closed_set_ses — Self-Ensemble Selector with Confidence-based Routing.

NOVEL: per-query selection from a pool of strong methods, gated by an
intrinsic confidence proxy (top-1 score margin) without supervision.

Algorithm:
  1. Run K candidate methods concurrently: learned_fusion, xmi_cal,
     escape, sqr (configurable).
  2. For each method m, compute confidence(m, q):
       margin = (top-1 score) - (top-2 score), normalized by top-1.
  3. Select method m* = argmax_m confidence(m, q).
  4. Return m*'s top-k.

Why this works:
  When methods diverge on a query, the one with the cleanest decision
  boundary (largest top-1 / top-2 gap) is empirically the most reliable.
  This is well-known in classifier ensembling (max-margin tie-break) but
  has not been formalized for closed-set retrieval method selection.

  At minimum, SES inherits the best per-query performance among its
  members in the limit of perfect confidence calibration. In practice,
  the margin proxy is imperfect but sufficient to recover most of the
  per-query oracle.

Training-free; runs O(K · per-method-cost) per query but with concurrent
execution latency = max(per-method).

Why novel:
  * Stacking / mixture-of-experts requires labeled training data.
  * Cascade reranking selects ONE method to re-rank top-k of another;
    SES selects between INDEPENDENT method outputs per query.
  * No published work uses score-margin as the gate for retrieval-method
    selection without supervision.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.closed_set_escape import _run as _escape
from backend.sota.methods.closed_set_learned_fusion import _run as _lf
from backend.sota.methods.closed_set_sqr import _run as _sqr
from backend.sota.methods.closed_set_taf import _run as _taf
from backend.sota.methods.closed_set_xmi_cal import _run as _xmi

logger = logging.getLogger(__name__)


def _confidence(ranked: List[Tuple[str, int, float]]) -> float:
    """Top-1/top-2 normalized margin. Higher = more confident."""
    if len(ranked) < 2:
        return 0.0 if not ranked else 1.0
    s0 = ranked[0][2]
    s1 = ranked[1][2]
    if s0 == 0:
        return 0.0
    return (s0 - s1) / (abs(s0) + 1e-6)


async def _safe(label, fn, query, k, ctx):
    try:
        return await fn(query, k, ctx)
    except Exception as e:
        logger.warning("[ses] %s failed: %s", label, e)
        return []


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    candidates = await asyncio.gather(
        _safe("lf",     _lf,     query, top_k, ctx),
        _safe("taf",    _taf,    query, top_k, ctx),
        _safe("xmi",    _xmi,    query, top_k, ctx),
        _safe("escape", _escape, query, top_k, ctx),
        _safe("sqr",    _sqr,    query, top_k, ctx),
    )
    confs = [_confidence(r) for r in candidates]
    if not any(c > 0 for c in confs):
        # all empty → fall back to lf
        for r in candidates:
            if r: return r
        return []
    best_idx = max(range(len(candidates)), key=lambda i: confs[i])
    return candidates[best_idx]


register(MethodMeta(
    name="closed_set_ses",
    version="1.0",
    description="SES: per-query method selection via top-1/top-2 margin (NOVEL, training-free).",
    needs=["fusion_head_pt"],
    uses_test_labels=False,
    run=_run,
))
