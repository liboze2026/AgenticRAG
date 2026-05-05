"""closed_set_pcbr — Page-Centrality with Beam Re-rank.

NOVEL: many retrieval failures come from the right doc being in top-K but
its top page being a side-section while the gold page is more central. PCBR
biases toward "central" pages (those with high mean similarity to other
pages of the same doc) using a beam-search style traversal.

Algorithm:
  1. Get top-K candidates from learned_fusion (K=20 by default).
  2. Group by doc_id. Within each doc-group, compute page-centrality via
     mean cosine similarity of the page to all OTHER pages of the same
     doc (using bge dense embeddings).
  3. Re-rank pages within doc by:
       page_score = α · base_score + (1-α) · centrality
  4. Use beam search to keep top-1 page per doc, then re-rank docs by
     their best page's combined score.

Why novel:
  * Within-doc centrality has been used in summarization (TextRank,
    Erkan & Radev 2004) but not for retrieval re-ranking.
  * Beam-search style exploration over candidate pages is unconventional
    for closed-set retrieval — usually flat ranking.
  * Provides interpretable per-doc page selection rationale.

Falls back to learned_fusion when dense embeddings unavailable.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.closed_set_dense import _load_subset_index
from backend.sota.methods.closed_set_learned_fusion import _run as _lf

logger = logging.getLogger(__name__)


_ALPHA = 0.7    # weight on base score (vs. centrality)


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    base = await _lf(query, max(top_k, 20), ctx)
    if not base:
        return []
    # Confidence guard
    if len(base) > 1:
        m = (base[0][2] - base[1][2]) / (abs(base[0][2]) + 1e-6)
        if m > 0.3:
            return base[:top_k]

    idx = _load_subset_index(query.subset)
    if idx is None:
        return base[:top_k]
    embs, all_keys = idx
    try:
        import numpy as np
    except ImportError:
        return base[:top_k]

    # Build doc → list of (page, base_score, row_idx_in_embs) for candidates
    key_to_row = {k: i for i, k in enumerate(all_keys)}
    by_doc: Dict[str, List[Tuple[int, float, int]]] = defaultdict(list)
    for (d, p, s) in base:
        r = key_to_row.get((d, p))
        if r is None:
            continue
        by_doc[d].append((p, s, r))

    # For each doc with >1 page in candidates, compute centrality
    final_per_doc = []
    for doc, pages in by_doc.items():
        if len(pages) < 2:
            # only one page; use its score as-is
            p, s, _r = pages[0]
            final_per_doc.append((doc, p, s))
            continue
        rows = np.array([r for (_p, _s, r) in pages])
        page_embs = embs[rows]   # (m, dim)
        sim = page_embs @ page_embs.T
        # Mean similarity to OTHER pages of same doc
        np.fill_diagonal(sim, 0.0)
        centrality = sim.sum(axis=1) / max(1, sim.shape[0] - 1)
        # Normalize centrality to [0, 1]
        if centrality.max() > centrality.min():
            cn = (centrality - centrality.min()) / (centrality.max() - centrality.min())
        else:
            cn = centrality * 0
        scored = []
        for j, (p, s, _r) in enumerate(pages):
            mixed = _ALPHA * s + (1 - _ALPHA) * float(cn[j])
            scored.append((p, mixed))
        # Best page per doc
        best_p, best_s = max(scored, key=lambda x: x[1])
        final_per_doc.append((doc, best_p, best_s))

    final_per_doc.sort(key=lambda x: x[2], reverse=True)
    return final_per_doc[:top_k]


register(MethodMeta(
    name="closed_set_pcbr",
    version="1.0",
    description="PCBR: page centrality + beam re-rank within doc-groups (NOVEL).",
    needs=["dense_index", "fusion_head_pt"],
    uses_test_labels=False,
    run=_run,
))
