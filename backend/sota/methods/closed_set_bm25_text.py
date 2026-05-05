"""Closed-set BM25 over per-doc full text.

Uses VisDomCorpus to fetch each candidate's full text, builds an in-memory
BM25 over the candidate set per query, returns top-k by BM25 score.

Falls back to title-only if the corpus isn't available for the subset.
"""
from __future__ import annotations

import logging
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.closed_set_titlematch import _bm25_scores, _tokenize

logger = logging.getLogger(__name__)


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    candidates = (query.metadata or {}).get("candidate_docs", []) or []
    if not candidates:
        return []
    corpus = (ctx.extras or {}).get("corpus") if ctx.extras else None
    if corpus is None or not corpus.is_available(query.subset):
        # graceful fallback: use titles only
        from backend.sota.methods.closed_set_titlematch import _run as _title
        return await _title(query, top_k, ctx)

    q_tokens = _tokenize(query.query)
    docs_tokens: List[List[str]] = []
    available_candidates: List[str] = []
    for doc_id in candidates:
        text = corpus.doc_text(query.subset, doc_id)
        if text is None:
            # use title only as fallback for missing docs
            docs_tokens.append(_tokenize(doc_id))
        else:
            # cap text length to avoid pathological cases (slide decks etc.)
            docs_tokens.append(_tokenize(text[:200_000]))
        available_candidates.append(doc_id)

    scores = _bm25_scores(docs_tokens, q_tokens)
    ranked = sorted(zip(available_candidates, scores), key=lambda kv: kv[1], reverse=True)
    return [(c, 1, float(s)) for (c, s) in ranked[:top_k]]


register(MethodMeta(
    name="closed_set_bm25_text",
    version="1.0",
    description="BM25 over candidate full doc text within per-query closed set.",
    needs=["visdom_corpus"],
    uses_test_labels=False,
    run=_run,
))
