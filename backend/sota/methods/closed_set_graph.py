"""Closed-set candidate-page graph propagation.

Pipeline:
  1. Get top-K initial candidates from learned_fusion (default K=20)
  2. Build similarity graph over those K pages using dense embeddings
     (cosine similarity, threshold = 0.5; sparse k-NN with k=5).
  3. Personalized PageRank with the query as the personalization vector
     (seed score from learned_fusion).
  4. Re-rank by stationary distribution. Return top-k.

Idea: pages near-duplicate (e.g. consecutive slides describing one
concept) reinforce each other and pull each other up the ranking.
This helps when the gold page is in a "cluster" with non-gold but similar
pages — the cluster as a whole wins, and within it the original
fusion-head signal picks the actual gold.

Falls back to learned_fusion when dense embeddings missing.
"""
from __future__ import annotations

import logging
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.closed_set_dense import _load_subset_index
from backend.sota.methods.closed_set_learned_fusion import _run as _lf

logger = logging.getLogger(__name__)


def _personalized_pagerank(adj, seed, alpha=0.85, n_iter=20):
    """adj: (N, N) row-normalized adjacency. seed: (N,) personalization."""
    import numpy as np
    p = seed / (seed.sum() + 1e-9)
    for _ in range(n_iter):
        p = alpha * (adj @ p) + (1 - alpha) * (seed / (seed.sum() + 1e-9))
        p /= (p.sum() + 1e-9)
    return p


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    K = max(20, top_k * 4)
    seed_results = await _lf(query, K, ctx)
    if not seed_results:
        return []

    idx = _load_subset_index(query.subset)
    if idx is None:
        return seed_results[:top_k]

    embs, all_keys = idx
    try:
        import numpy as np
    except ImportError:
        return seed_results[:top_k]

    # Map seed_results page-keys to embedding rows
    key_to_row = {k: i for i, k in enumerate(all_keys)}
    rows = []
    cand_keys = []
    seed_scores = []
    for (d, p, s) in seed_results:
        r = key_to_row.get((d, p))
        if r is None:
            continue
        rows.append(r)
        cand_keys.append((d, p))
        seed_scores.append(s)
    if len(rows) < 2:
        return seed_results[:top_k]

    cand_embs = embs[rows]  # (M, 768) normalized
    sim = cand_embs @ cand_embs.T  # cosine since normalized
    # Drop self-loops + threshold
    np.fill_diagonal(sim, 0.0)
    sim = np.where(sim > 0.5, sim, 0.0)
    # Row-normalize (transition matrix)
    row_sum = sim.sum(axis=1, keepdims=True) + 1e-9
    adj = sim / row_sum

    seed_arr = np.array(seed_scores, dtype="float64")
    if seed_arr.min() < 0:
        seed_arr = seed_arr - seed_arr.min()
    pr = _personalized_pagerank(adj, seed_arr, alpha=0.85, n_iter=20)

    order = pr.argsort()[::-1][:top_k]
    return [(cand_keys[i][0], cand_keys[i][1], float(pr[i])) for i in order]


register(MethodMeta(
    name="closed_set_graph",
    version="1.0",
    description="Personalized PageRank over top-K candidate similarity graph (seed = learned_fusion).",
    needs=["dense_index", "fusion_head_pt"],
    uses_test_labels=False,
    run=_run,
))
