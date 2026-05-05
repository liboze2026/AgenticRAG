"""Closed-set page-level BM25.

For each candidate doc, scores every page individually and ranks all
(doc, page) pairs across the candidate set. Returns top-k pairs.

Critical for slidevqa where gold is at the page level (e.g. evidence_pages=[4]).
For doc-level subsets (feta_tab, paper_tab, etc.) the gold is page=1, and
this method's first-page hit usually matches what doc-level methods would
return — but with page-level granularity available for analysis.
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
        # Fallback: page=1 doc text BM25 (or title)
        from backend.sota.methods.closed_set_bm25_text import _run as _doc
        return await _doc(query, top_k, ctx)

    q_tokens = _tokenize(query.query)
    page_keys: List[Tuple[str, int]] = []
    page_token_lists: List[List[str]] = []
    for doc_id in candidates:
        pages = corpus.doc_pages(query.subset, doc_id)
        if not pages:
            page_keys.append((doc_id, 1))
            page_token_lists.append(_tokenize(doc_id))
            continue
        for (pn, text) in pages:
            page_keys.append((doc_id, pn))
            page_token_lists.append(_tokenize(text[:50_000]))

    scores = _bm25_scores(page_token_lists, q_tokens)
    ranked = sorted(zip(page_keys, scores), key=lambda kv: kv[1], reverse=True)[:top_k]
    return [(d, p, float(s)) for ((d, p), s) in ranked]


register(MethodMeta(
    name="closed_set_bm25_page",
    version="1.0",
    description="Page-level BM25 over candidate docs (essential for slidevqa).",
    needs=["visdom_corpus"],
    uses_test_labels=False,
    run=_run,
))
