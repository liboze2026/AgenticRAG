"""Closed-set BM25-on-titles baseline.

Builds an in-memory BM25 over the candidate_docs IDs (treated as titles)
and scores them against the query. Cheap, instant, no external corpus.

Tokenization: same bilingual scheme as backend/strategies/retrievers/bm25.py
(latin words + CJK unigram+bigram). Many VisDoM doc IDs are descriptive
strings (e.g. wiki article titles, paper IDs, deck names with words),
so title-match alone often captures non-trivial signal.
"""
from __future__ import annotations

import logging
import math
import re
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register

logger = logging.getLogger(__name__)


_TOK_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]+")
_CN_RE = re.compile(r"[一-鿿㐀-䶿]+")


def _tokenize(text: str) -> List[str]:
    text = (text or "").lower().replace("_", " ").replace("-", " ").replace(".", " ")
    out: List[str] = list(_TOK_RE.findall(text))
    for run in _CN_RE.findall(text):
        out.extend(list(run))
        out.extend(run[i:i + 2] for i in range(len(run) - 1))
    return out


def _bm25_scores(
    docs_tokens: List[List[str]], query_tokens: List[str],
    k1: float = 1.5, b: float = 0.75,
) -> List[float]:
    n = len(docs_tokens)
    if n == 0 or not query_tokens:
        return [0.0] * n
    avgdl = sum(len(d) for d in docs_tokens) / n if n else 1.0
    df: dict = {}
    for d in docs_tokens:
        for tok in set(d):
            df[tok] = df.get(tok, 0) + 1
    scores = []
    for d in docs_tokens:
        dl = len(d) or 1
        s = 0.0
        for q in query_tokens:
            if q not in df:
                continue
            f = d.count(q)
            if f == 0:
                continue
            idf = math.log((n - df[q] + 0.5) / (df[q] + 0.5) + 1.0)
            tf = f * (k1 + 1) / (f + k1 * (1 - b + b * dl / avgdl))
            s += idf * tf
        scores.append(s)
    return scores


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    candidates = (query.metadata or {}).get("candidate_docs", []) or []
    if not candidates:
        return []
    q_tokens = _tokenize(query.query)
    docs_tokens = [_tokenize(c) for c in candidates]
    scores = _bm25_scores(docs_tokens, q_tokens)
    ranked = sorted(zip(candidates, scores), key=lambda kv: kv[1], reverse=True)[:top_k]
    return [(c, 1, float(s)) for (c, s) in ranked]


register(MethodMeta(
    name="closed_set_titlematch",
    version="1.0",
    description="BM25 over candidate_docs IDs (titles/filenames) within per-query closed set.",
    needs=[],
    uses_test_labels=False,
    run=_run,
))
