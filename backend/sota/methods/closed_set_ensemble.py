"""Closed-set super-ensemble: RRF fuse all available text-side channels.

Channels (skipped silently if their dependencies are missing):
  * closed_set_bm25_page    sparse text
  * closed_set_dense        dense text (bge-base)
  * closed_set_hyde         dense + LLM hypothetical doc
  * closed_set_titlematch   surface-form filename signal

This is the strongest text-only ensemble in Phase 1. Phase 2 will train a
learned fusion head; for now we use uniform-weight RRF.

Channels are run concurrently via asyncio.gather so end-to-end latency is
roughly the slowest channel, not their sum.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.baseline_rrf import _rrf_fuse
from backend.sota.methods.closed_set_bm25_page import _run as _bm
from backend.sota.methods.closed_set_dense import _run as _de
from backend.sota.methods.closed_set_hyde import _run as _hy
from backend.sota.methods.closed_set_titlematch import _run as _ti

logger = logging.getLogger(__name__)


async def _safe_run(label, fn, query, k, ctx):
    try:
        out = await fn(query, k, ctx)
        return [(d, p) for (d, p, _s) in out]
    except Exception as e:
        logger.warning("[ensemble] %s failed: %s", label, e)
        return []


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    k = top_k * 2
    a, b, c, d = await asyncio.gather(
        _safe_run("bm25_page", _bm, query, k, ctx),
        _safe_run("dense",     _de, query, k, ctx),
        _safe_run("hyde",      _hy, query, k, ctx),
        _safe_run("title",     _ti, query, k, ctx),
    )
    return _rrf_fuse([a, b, c, d], k=60, top_k=top_k)


register(MethodMeta(
    name="closed_set_ensemble",
    version="1.0",
    description="RRF super-ensemble: bm25_page ⊕ dense ⊕ hyde ⊕ titlematch (concurrent).",
    needs=["visdom_corpus", "dense_index"],
    uses_test_labels=False,
    run=_run,
))
