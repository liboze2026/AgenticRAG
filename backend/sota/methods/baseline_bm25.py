"""BM25 baseline: reuses lab/hybrid BM25 index, read-only."""
from __future__ import annotations

import logging
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register

logger = logging.getLogger(__name__)


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    """Corpus-wide BM25 retrieval against the lab's BM25 index.

    Sees only docs already indexed into the main pipeline (lab.hybrid syncs
    against documents.db). For VisDoMBench docs not in the main system,
    returns empty — see `closed_set_*` methods for closed-set BM25.
    """
    lab = ctx.lab_bundle
    if lab is None or lab.hybrid is None:
        raise RuntimeError("lab BM25 service unavailable")
    await lab.hybrid._ensure_bm25_synced()
    hits = await lab.hybrid.bm25.retrieve_text(query.query, top_k=top_k)
    return [(h.document_id, h.page_number, float(h.score)) for h in hits]


register(MethodMeta(
    name="baseline_bm25",
    version="1.0",
    description="BM25 sparse text retrieval over OCR'd page text.",
    needs=["lab_bundle.hybrid"],
    uses_test_labels=False,
    run=_run,
))
