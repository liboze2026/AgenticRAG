"""closed_set_sqr — Specificity-Quotient Re-ranking.

NOVEL: candidates that score high for the actual query AND for many other
unrelated queries are 'generic' — high IDF in queryland, low information
about THIS query. Re-rank by SPECIFICITY = sim(q, d) − E_q'~Decoy[ sim(q', d) ].

Decoy queries are sampled from the train split (NOT test), so this is
calibrated and integrity-safe.

Theoretical motivation:
  Define generic_score(d) = E_q'[s(q', d)] over query distribution.
  Specificity(q, d) = s(q, d) − generic_score(d).
  This is mathematically equivalent to TFIDF generalization to dense
  retrieval — IDF is approximated empirically via Monte Carlo over
  decoy queries from the training distribution.

  In closed-set retrieval, generic pages (e.g. survey-like content)
  often dominate top-K under many queries; SQR explicitly demotes them.

Compute cost: per query, encode |Decoy| dense vectors once at startup
(amortized), then specificity = K dot products + subtraction.

Why novel:
  * Score normalization in IR (Manning 2008) usually normalizes
    distributions across documents, not via decoy queries.
  * Diversity-aware re-ranking (Carbonell 1998 MMR) penalizes
    redundancy, not genericness — orthogonal idea.
  * Counterfactual / saliency-based scoring exists in classification
    (LIME, SHAP) but not in dense retrieval re-ranking.

Falls back to learned_fusion when no dense index or training corpus exists.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Dict, List, Optional, Tuple

from backend.sota.datasets import load_local_queries
from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.closed_set_dense import (
    _load_query_encoder, _load_subset_index,
)
from backend.sota.methods.closed_set_learned_fusion import _run as _lf

logger = logging.getLogger(__name__)


_DECOY_LOCK = threading.Lock()
_DECOY_VECS: Dict[str, object] = {}     # subset → (N, dim) numpy
_DECOY_QUERIES: Dict[str, List[str]] = {}
_DATA_ROOT = os.path.join("data", "sota_runs", "datasets")
_N_DECOY = 64


def _load_decoy(subset: str):
    if subset in _DECOY_VECS:
        return _DECOY_VECS[subset]
    with _DECOY_LOCK:
        if subset in _DECOY_VECS:
            return _DECOY_VECS[subset]
        encoder = _load_query_encoder()
        if not encoder:
            _DECOY_VECS[subset] = None
            return None
        try:
            import numpy as np
        except ImportError:
            _DECOY_VECS[subset] = None
            return None
        # Pull up to _N_DECOY queries from TRAIN split only.
        train_qs = list(load_local_queries(_DATA_ROOT, subset, limit=_N_DECOY, split="train"))
        if not train_qs:
            _DECOY_VECS[subset] = None
            return None
        texts = [("query: " + q.query)[:500] for q in train_qs]
        vecs = encoder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        _DECOY_VECS[subset] = np.asarray(vecs, dtype="float32")
        _DECOY_QUERIES[subset] = [q.query for q in train_qs]
        logger.info("[sqr] decoy %s: %d train queries cached", subset, len(train_qs))
        return _DECOY_VECS[subset]


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    base = await _lf(query, max(top_k, 20), ctx)
    if not base:
        return []
    idx = _load_subset_index(query.subset)
    decoy = _load_decoy(query.subset)
    if idx is None or decoy is None:
        return base[:top_k]
    encoder = _load_query_encoder()
    if not encoder:
        return base[:top_k]

    embs, all_keys = idx
    try:
        import numpy as np
    except ImportError:
        return base[:top_k]

    key_to_row = {k: i for i, k in enumerate(all_keys)}
    rows = []
    cand_keys = []
    base_scores = []
    for (d, p, s) in base:
        r = key_to_row.get((d, p))
        if r is None:
            continue
        rows.append(r)
        cand_keys.append((d, p))
        base_scores.append(s)
    if not rows:
        return base[:top_k]

    cand_embs = embs[rows]                              # (M, dim)
    base_arr = np.asarray(base_scores, dtype="float32") # (M,)

    q_vec = encoder.encode([("query: " + query.query)[:500]],
                           normalize_embeddings=True, show_progress_bar=False)[0]
    sim_q = cand_embs @ q_vec                          # (M,)
    # Decoy: avg over decoy queries → genericness
    decoy_sims = cand_embs @ decoy.T                   # (M, N_decoy)
    generic = decoy_sims.mean(axis=1)                  # (M,)

    # Specificity
    spec = sim_q - generic                             # (M,)
    # Combine with base learned_fusion score (rank), specificity is bonus
    base_rank = (-base_arr).argsort().argsort().astype("float32")  # 0=top
    # Spec normalized (z-score)
    if spec.std() > 1e-6:
        spec_z = (spec - spec.mean()) / spec.std()
    else:
        spec_z = spec * 0.0
    final = -base_rank + 1.5 * spec_z                  # higher better

    order = final.argsort()[::-1][:top_k]
    return [(cand_keys[i][0], cand_keys[i][1], float(final[i])) for i in order]


register(MethodMeta(
    name="closed_set_sqr",
    version="1.0",
    description="SQR: re-rank by specificity = sim(q,d) − E_decoy[sim(q',d)] (NOVEL, train-decoy).",
    needs=["dense_index", "fusion_head_pt"],
    uses_test_labels=False,
    run=_run,
))
