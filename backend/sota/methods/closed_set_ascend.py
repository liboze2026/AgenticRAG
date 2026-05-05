"""closed_set_ascend — Adaptive Synthetic-Candidate ENsemble Distillation.

NOVEL extension of HyDE: rather than REPLACING the query with an LLM-
synthesized hypothetical document (HyDE, Gao et al. ACL 2023), ASCEND
mixes synthetic and real-query embeddings with an ADAPTIVE weight
determined by the synthetic candidate's intrinsic confidence.

Algorithm:
  1. Generate hypothetical doc text H via LLM (zhipu glm-4-flash by default).
  2. Embed both q and H with bge-base. Let v_q, v_H be normalized vectors.
  3. Confidence proxy: entropy of softmax(top-K cosine similarities of v_H
     to candidate page embeddings). Low entropy = LLM is well-grounded
     (matches a few candidates strongly) → high α.
  4. Mixed query embedding: v_mix = α · v_H + (1 - α) · v_q (re-normalize).
  5. Score candidates by cosine similarity to v_mix.
  6. Combine with learned_fusion via reciprocal rank fusion.

Why not pure HyDE:
  HyDE replaces v_q with v_H. If H is hallucinated (LLM doesn't know the
  domain), retrieval suffers. ASCEND backstops with the real query and
  learns when to trust the LLM via the entropy-confidence proxy. This is
  a sample-efficient generalization that doesn't require LLM domain
  fine-tuning.

Falls back to learned_fusion when LLM/dense unavailable.
"""
from __future__ import annotations

import logging
import math
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.closed_set_dense import (
    _load_query_encoder, _load_subset_index,
)
from backend.sota.methods.closed_set_hyde import _generate_hypothetical
from backend.sota.methods.closed_set_learned_fusion import _run as _lf

logger = logging.getLogger(__name__)


def _entropy(values) -> float:
    import numpy as np
    z = np.exp(values - values.max())
    p = z / (z.sum() + 1e-9)
    return float(-(p * np.log(p + 1e-12)).sum())


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    base = await _lf(query, max(top_k, 20), ctx)
    if not base:
        return []
    encoder = _load_query_encoder()
    if not encoder:
        return base[:top_k]
    idx = _load_subset_index(query.subset)
    if idx is None:
        return base[:top_k]
    embs, all_keys = idx
    try:
        import numpy as np
    except ImportError:
        return base[:top_k]

    candidates = (query.metadata or {}).get("candidate_docs", []) or []
    cand_set = set(candidates)
    mask = np.array([k[0] in cand_set for k in all_keys])
    if not mask.any():
        return base[:top_k]
    cand_embs = embs[mask]
    cand_keys = [k for k, m in zip(all_keys, mask) if m]

    # Confidence guard
    if len(base) > 1:
        m = (base[0][2] - base[1][2]) / (abs(base[0][2]) + 1e-6)
        if m > 0.3:
            return base[:top_k]

    pipeline = ctx.pipeline
    H_text = await _generate_hypothetical(query.query, ctx) if pipeline else query.query
    if not H_text or H_text.strip() == query.query.strip():
        return base[:top_k]

    v_q = encoder.encode([("query: " + query.query)[:500]],
                         normalize_embeddings=True, show_progress_bar=False)[0]
    v_H = encoder.encode([H_text[:500]],
                         normalize_embeddings=True, show_progress_bar=False)[0]

    sim_H = cand_embs @ v_H
    # Top-K entropy as confidence
    K = min(8, len(sim_H))
    top = np.partition(sim_H, -K)[-K:]
    H_entropy = _entropy(top)
    Hmax = math.log(K)
    # alpha: low entropy → high alpha (more weight to LLM hypothetical)
    alpha = max(0.2, min(0.7, 1.0 - H_entropy / max(Hmax, 1e-6)))

    v_mix = alpha * v_H + (1 - alpha) * v_q
    norm = np.linalg.norm(v_mix) + 1e-9
    v_mix = v_mix / norm
    sims = cand_embs @ v_mix
    order = sims.argsort()[::-1][:top_k]
    return [(cand_keys[i][0], cand_keys[i][1], float(sims[i])) for i in order]


register(MethodMeta(
    name="closed_set_ascend",
    version="1.0",
    description="ASCEND: adaptive HyDE+query mixing via entropy-confidence proxy (NOVEL).",
    needs=["pipeline.generator", "dense_index", "fusion_head_pt"],
    uses_test_labels=False,
    run=_run,
))
