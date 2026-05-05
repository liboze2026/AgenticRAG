"""Closed-set text-only RRF: bm25_text ⊕ titlematch ⊕ bm25_page.

All three legs are content/title-text based and run cheap and offline.
RRF averages their rankings, so a method that wins big on one subset
(e.g. titlematch on feta_tab, bm25_text on paper_tab/spiqa) lifts the
ensemble's average without dragging the others down too much.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.baseline_rrf import _rrf_fuse
from backend.sota.methods.closed_set_bm25_page import _run as _bm25_page
from backend.sota.methods.closed_set_bm25_text import _run as _bm25_text
from backend.sota.methods.closed_set_titlematch import _run as _title

logger = logging.getLogger(__name__)


async def _safe(label, fn, query, k, ctx):
    try:
        out = await fn(query, k, ctx)
        return [(d, p) for (d, p, _s) in out]
    except Exception as e:
        logger.warning("[text_rrf] %s failed: %s", label, e)
        return []


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    k = top_k * 2
    a, b, c = await asyncio.gather(
        _safe("bm25_text", _bm25_text, query, k, ctx),
        _safe("titlematch", _title, query, k, ctx),
        _safe("bm25_page", _bm25_page, query, k, ctx),
    )
    return _rrf_fuse([a, b, c], k=60, top_k=top_k)


register(MethodMeta(
    name="closed_set_text_rrf",
    version="1.0",
    description="RRF fusion of bm25_text + titlematch + bm25_page (text-only, no embeddings).",
    needs=["visdom_corpus"],
    uses_test_labels=False,
    run=_run,
))
