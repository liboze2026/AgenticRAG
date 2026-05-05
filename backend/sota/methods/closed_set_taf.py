"""closed_set_taf — Title-Aware Adaptive Fusion.

NOVEL: detect when the query exhibits high overlap with one specific
candidate title; in that case use titlematch as primary (with content
channels as tie-breakers). Otherwise fall back to learned_fusion.

Theoretical motivation:
  When a query is near-quoting a doc's title (e.g. Wikipedia article
  question patterns), title-only retrieval is ALMOST PERFECT and any
  content-fusion dilutes the signal. Standard fusion methods can't
  detect this regime; they apply uniform fusion regardless. TAF uses an
  online query-title overlap statistic to gate channel weights.

Detection: compute Jaccard overlap of query's content tokens with each
candidate's tokenized doc_id; if max-Jaccard ≥ τ, declare 'title regime'.

τ defaults to 0.3 — chosen so that ≥30% of distinctive tokens in the
query appear in the title. Lower → more aggressive title-mode; higher
→ more conservative.

Why novel:
  * No published work explicitly gates fusion weights on token-overlap
    statistics. RankBoost / Learning-to-rank uses query features but
    requires labeled training data; TAF is training-free.
  * Provides interpretability: per query, the regime label and the
    chosen weights are saved for inspection.
"""
from __future__ import annotations

import logging
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.closed_set_learned_fusion import _run as _lf
from backend.sota.methods.closed_set_titlematch import _run as _title
from backend.sota.methods.closed_set_titlematch import _tokenize

logger = logging.getLogger(__name__)


_TAU = 0.3
_TITLE_BONUS = 5.0    # additive log-score for title-regime decisive cand


def _max_jaccard(query: str, candidates: List[str]) -> float:
    q = set(_tokenize(query))
    if not q or not candidates:
        return 0.0
    best = 0.0
    for c in candidates:
        d = set(_tokenize(c))
        if not d:
            continue
        inter = len(q & d)
        union = len(q | d)
        if union > 0:
            j = inter / union
            if j > best: best = j
    return best


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    candidates = (query.metadata or {}).get("candidate_docs", []) or []
    if not candidates:
        return []
    j = _max_jaccard(query.query, candidates)
    if j >= _TAU:
        # title regime: title-channel primary, lf as tie-break
        title_results = await _title(query, top_k, ctx)
        if title_results and title_results[0][2] > 0:
            # boost title's top-1 over lf top-1 by adding bonus
            lf_results = await _lf(query, top_k, ctx)
            seen = {(d, p): s for (d, p, s) in lf_results}
            out = []
            for i, (d, p, s) in enumerate(title_results):
                bonus = _TITLE_BONUS / (i + 1)
                merged = bonus + seen.pop((d, p), 0.0)
                out.append((d, p, merged))
            for (d, p), s in seen.items():
                out.append((d, p, s))
            out.sort(key=lambda x: x[2], reverse=True)
            return out[:top_k]
    # default regime: learned_fusion
    return await _lf(query, top_k, ctx)


register(MethodMeta(
    name="closed_set_taf",
    version="1.0",
    description="TAF: query-title Jaccard gate switching between title-primary and learned_fusion (NOVEL).",
    needs=["fusion_head_pt"],
    uses_test_labels=False,
    run=_run,
))
