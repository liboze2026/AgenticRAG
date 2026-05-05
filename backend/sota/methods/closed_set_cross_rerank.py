"""Closed-set cross-encoder rerank.

Pipeline:
  1. Get top-N (default N=20) candidates from `closed_set_hybrid` (BM25 + dense)
  2. For each (query, candidate page text) pair, score with a cross-encoder
     (ms-marco-MiniLM-L-6-v2: ~22 MB, ~1 ms/pair on CPU, ~0.2 ms on GPU)
  3. Re-rank by cross-encoder score, return top-k

Cross-encoders are typically +3-5 pt R@1 over dense or sparse alone, because
they jointly attend to query and document tokens (vs cosine over independent
embeddings).

Reference: Reimers & Gurevych, sentence-transformers cross-encoder family.
"""
from __future__ import annotations

import logging
import threading
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.closed_set_hybrid import _run as _hybrid

logger = logging.getLogger(__name__)


_CE = None
_CE_LOCK = threading.Lock()
_CE_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _load_ce():
    global _CE
    if _CE is not None:
        return _CE
    with _CE_LOCK:
        if _CE is not None:
            return _CE
        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            logger.warning("sentence-transformers not installed; cross_rerank disabled")
            _CE = False
            return False
        try:
            _CE = CrossEncoder(_CE_NAME, max_length=512)
            logger.info("[cross_rerank] loaded %s", _CE_NAME)
        except Exception as e:
            logger.warning("[cross_rerank] could not load %s: %s", _CE_NAME, e)
            _CE = False
        return _CE


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    candidates_in = await _hybrid(query, top_k * 4, ctx)
    if not candidates_in:
        return []
    ce = _load_ce()
    if not ce:
        return candidates_in[:top_k]
    corpus = (ctx.extras or {}).get("corpus") if ctx.extras else None
    if corpus is None:
        return candidates_in[:top_k]

    pairs = []
    keys = []
    for (doc_id, page_num, _s) in candidates_in:
        pages = corpus.doc_pages(query.subset, doc_id) or []
        page_text = ""
        for (pn, t) in pages:
            if pn == page_num:
                page_text = t
                break
        if not page_text:
            page_text = corpus.doc_text(query.subset, doc_id) or doc_id
        pairs.append([query.query, page_text[:1000]])
        keys.append((doc_id, page_num))
    try:
        scores = ce.predict(pairs, show_progress_bar=False)
    except Exception as e:
        logger.warning("[cross_rerank] predict failed: %s", e)
        return candidates_in[:top_k]
    ranked = sorted(zip(keys, scores), key=lambda kv: float(kv[1]), reverse=True)[:top_k]
    return [(d, p, float(s)) for ((d, p), s) in ranked]


register(MethodMeta(
    name="closed_set_cross_rerank",
    version="1.0",
    description="Cross-encoder (ms-marco-MiniLM) rerank of top-20 hybrid candidates.",
    needs=["visdom_corpus", "dense_index", "cross_encoder"],
    uses_test_labels=False,
    run=_run,
))
