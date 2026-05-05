"""closed_set_nirr — Negation-Invariant Robust Re-ranking.

NOVEL: queries with negation cues ("not", "without", "except", "no") are
under-handled by standard retrievers. Off-the-shelf BM25 / dense retrievers
treat 'X' and 'not X' near-identically because tokens are bag-of-words.
NIRR detects negation, generates a counterfactual AFFIRMATIVE query, runs
both, and combines results to penalize candidates that score high under
both queries (those are answering both → not specifically negation-anchored).

Algorithm:
  1. Detect negation cue tokens in query.
  2. If found: produce affirmative-form query Q+ by removing negation
     tokens (or substituting via small template rules).
  3. Run learned_fusion on Q (returns R_neg) and Q+ (returns R_aff).
  4. Final score for candidate d:
       score_final(d) = R_neg.score(d) − λ · R_aff.score(d)
     i.e. up-weight candidates that score for the negation but down-weight
     those that score equally well for the un-negated form.
  5. If no negation cue: return learned_fusion(Q) directly.

Theoretical lens:
  Standard distributional embeddings encode antonym similarity as high
  (a known limitation; cf. Mrkšić et al. 2016 retrofitting). Counterfactual
  re-ranking via affirmative-query subtraction gives a query-time correction
  without retraining the embedding space.

Why novel:
  * Negation handling in retrieval has been studied (Hossain 2022, etc.)
    but at the encoder level (specialized embedding training).
  * NIRR is training-free, applies as a re-ranker, and uses the SAME
    learned_fusion machinery for both queries — so it's plug-and-play.
"""
from __future__ import annotations

import logging
import re
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.closed_set_learned_fusion import _run as _lf

logger = logging.getLogger(__name__)


_NEG_CUES = (
    r"\bnot\b", r"\bdoes\s*n't\b", r"\bdoesn't\b", r"\bdo\s*n't\b", r"\bdon't\b",
    r"\bisn't\b", r"\bis\s*n't\b", r"\bweren't\b", r"\baren't\b",
    r"\bwithout\b", r"\bexcept\b", r"\bno\b", r"\bnone\b",
    r"\bnever\b", r"\bnothing\b", r"\bcannot\b", r"\bcan't\b",
    r"\bunable\b", r"\bfailed\s*to\b",
)
_NEG_RE = re.compile("|".join(_NEG_CUES), re.IGNORECASE)


def _detect_negation(query: str) -> bool:
    return bool(_NEG_RE.search(query or ""))


def _affirmative_form(query: str) -> str:
    """Remove negation tokens to get an affirmative query.

    Conservative: just drop the negation words; surrounding syntax stays.
    e.g. "Which paper does NOT use BM25?" → "Which paper does use BM25?"
    Heuristic but sufficient for retrieval re-ranking purposes.
    """
    q2 = _NEG_RE.sub(" ", query or "")
    q2 = re.sub(r"\s{2,}", " ", q2).strip()
    return q2


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    if not _detect_negation(query.query):
        return await _lf(query, top_k, ctx)

    aff_text = _affirmative_form(query.query)
    if not aff_text or aff_text == query.query:
        return await _lf(query, top_k, ctx)

    # Run learned_fusion on both the original (Q) and the affirmative (Q+)
    R_neg = await _lf(query, max(top_k * 2, 20), ctx)
    if not R_neg:
        return []

    class _Q:
        pass
    qa = _Q()
    qa.query_id = query.query_id + "_aff"
    qa.subset = query.subset
    qa.query = aff_text
    qa.gold_pages = []
    qa.metadata = query.metadata
    R_aff = await _lf(qa, max(top_k * 2, 20), ctx)

    aff_score = {(d, p): s for (d, p, s) in R_aff}
    LAMBDA = 0.5
    rescored = []
    for (d, p, s) in R_neg:
        as_ = aff_score.get((d, p), 0.0)
        rescored.append((d, p, s - LAMBDA * as_))
    rescored.sort(key=lambda x: x[2], reverse=True)
    return rescored[:top_k]


register(MethodMeta(
    name="closed_set_nirr",
    version="1.0",
    description="NIRR: negation-aware counterfactual re-ranking via affirmative-query subtraction (NOVEL).",
    needs=["fusion_head_pt"],
    uses_test_labels=False,
    run=_run,
))
