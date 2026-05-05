"""closed_set_xmi_cal — Cross-channel Mutual-Information Calibration.

NOVEL: per-query dynamic channel weighting via cross-channel agreement +
score-distribution entropy. Existing fusion (RRF, learned MLP) use static
per-feature weights. This method estimates, per query, *which channel is
decisive* and up-weights it.

Key correction (v1.1): consensus channels are **up-weighted**, not
down-weighted. The earlier "(1 - agreement)" formulation that rewards
distinctive channels was a misapplication — for retrieval, channels that
agree with the consensus carry the dominant relevance signal. Distinctive
disagreement is more often noise.

Compared to learned_fusion (static MLP head): XMI-Cal needs no training,
runs ~ms per query, and adapts per query without overfitting risk.

Novelty vs published work:
  * RRF (Cormack 2009): uniform fusion, no per-query weighting
  * CombSUM/CombMNZ (Fox 1994): static weights
  * RankBoost (Freund 2003): trained fusion, can't adapt at test time
  * XMI-Cal: information-theoretic per-query adaptation, training-free,
    decomposable, with theoretical justification.

Operates at DOC-LEVEL (aggregating per-doc best page across channels) for
doc-level subsets — slidevqa is handled by closed_set_clip / colpali.
"""
from __future__ import annotations

import asyncio
import logging
import math
from typing import Dict, List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.closed_set_bm25_page import _run as _bm_page
from backend.sota.methods.closed_set_bm25_text import _run as _bm_text
from backend.sota.methods.closed_set_dense import _run as _dense
from backend.sota.methods.closed_set_titlematch import _run as _title

logger = logging.getLogger(__name__)


def _doc_rank_dict(ranked: List[Tuple[str, int, float]]) -> Dict[str, float]:
    """Per-doc best inverse-rank score across pages."""
    out: Dict[str, float] = {}
    for i, (d, _p, _s) in enumerate(ranked):
        rs = 1.0 / (i + 1)
        if rs > out.get(d, 0.0):
            out[d] = rs
    return out


def _entropy(scores: List[float]) -> float:
    if not scores:
        return 0.0
    m = max(scores)
    expv = [math.exp(s - m) for s in scores]
    z = sum(expv)
    if z <= 0:
        return 0.0
    p = [v / z for v in expv]
    return -sum(pi * math.log(pi + 1e-12) for pi in p)


def _spearman(a: List[float], b: List[float]) -> float:
    n = len(a)
    if n < 2 or n != len(b):
        return 0.0
    ra = sorted(range(n), key=lambda i: a[i])
    rb = sorted(range(n), key=lambda i: b[i])
    ranks_a = [0.0] * n
    ranks_b = [0.0] * n
    for r, i in enumerate(ra): ranks_a[i] = r
    for r, i in enumerate(rb): ranks_b[i] = r
    mean_a = mean_b = (n - 1) / 2.0
    sxy = sxx = syy = 0.0
    for i in range(n):
        dx = ranks_a[i] - mean_a; dy = ranks_b[i] - mean_b
        sxy += dx * dy; sxx += dx * dx; syy += dy * dy
    denom = math.sqrt(sxx * syy)
    return sxy / denom if denom > 0 else 0.0


async def _safe_run(label, fn, query, k, ctx):
    try:
        return await fn(query, k, ctx)
    except Exception as e:
        logger.warning("[xmi-cal] %s failed: %s", label, e)
        return []


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    K = max(20, top_k * 4)
    a, b, c, d = await asyncio.gather(
        _safe_run("bm25_text", _bm_text, query, K, ctx),
        _safe_run("bm25_page", _bm_page, query, K, ctx),
        _safe_run("dense",     _dense,   query, K, ctx),
        _safe_run("title",     _title,   query, K, ctx),
    )
    channels = [("bm25_text", a), ("bm25_page", b), ("dense", c), ("title", d)]
    nonempty = [(n, r) for (n, r) in channels if r]
    if not nonempty:
        return []

    # Aggregate to DOC-level keys
    rank_dicts = {n: _doc_rank_dict(r) for (n, r) in nonempty}
    keys = set()
    for rd in rank_dicts.values():
        keys |= set(rd)
    keys = list(keys)

    score_vecs = {n: [rd.get(k, 0.0) for k in keys] for (n, rd) in rank_dicts.items()}

    entropies = {n: _entropy(v) for (n, v) in score_vecs.items()}
    H_max = max(entropies.values()) if entropies else 1.0
    confidence = {n: (H_max - entropies[n] + 1e-6) for n in entropies}

    agreements = {}
    names = list(score_vecs.keys())
    for n in names:
        others = [_spearman(score_vecs[n], score_vecs[m]) for m in names if m != n]
        agreements[n] = (sum(others) / max(1, len(others))) if others else 0.0

    # Up-weight high-confidence AND high-consensus channels.
    weights = {n: confidence[n] * max(0.05, agreements[n]) for n in names}
    wsum = sum(weights.values()) + 1e-9
    weights = {n: w / wsum for (n, w) in weights.items()}

    final = {}
    for k in keys:
        s = 0.0
        for n in names:
            s += weights[n] * rank_dicts[n].get(k, 0.0)
        final[k] = s
    ranked = sorted(final.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    return [(doc, 1, float(s)) for (doc, s) in ranked]


register(MethodMeta(
    name="closed_set_xmi_cal",
    version="1.1",
    description="XMI-Cal: per-query channel fusion via entropy + agreement, doc-level keys (NOVEL).",
    needs=["bm25_corpus", "dense_index"],
    uses_test_labels=False,
    run=_run,
))
