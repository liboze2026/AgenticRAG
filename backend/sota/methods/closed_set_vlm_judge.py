"""Closed-set VLM-as-Judge top-k rerank.

Pipeline:
  1. Get top-N (default 10) from closed_set_learned_fusion (or hybrid as fallback)
  2. For each candidate, ask the pipeline.generator: "Does this page answer
     the query? Return a score 0–1."
  3. Re-rank by the LLM-judged score, return top-k.

Uses the existing pipeline.generator (zhipu glm-4v-flash by default in this
project). Single call per candidate, capped at N=8 to keep latency bounded.

Falls back to learned_fusion when no generator is available or LLM call fails.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.closed_set_learned_fusion import _run as _lf

logger = logging.getLogger(__name__)


_PROMPT = (
    "You are scoring how well a document page answers a user's question. "
    "Return ONLY a single number between 0 and 1 (no explanation). "
    "1 means the page directly contains the answer; 0 means unrelated.\n\n"
    "Question: {query}\n\n"
    "Page text (may be partial):\n{page}\n\n"
    "Score:"
)
_NUM_RE = re.compile(r"([0-9]*\.?[0-9]+)")


async def _llm_score(generator, prompt: str) -> float:
    """Best-effort numeric extraction from LLM. Returns 0 on any failure."""
    try:
        if hasattr(generator, "generate_text"):
            text = await generator.generate_text(prompt, max_tokens=8)
        else:
            from backend.models.schemas import RetrievalResult
            fake = [RetrievalResult(
                document_id="_judge", page_number=1, score=0.0,
                image_path="", layout=None,
            )]
            ans = await generator.generate(prompt, fake)
            text = getattr(ans, "text", None) or getattr(ans, "answer", None) or str(ans)
    except Exception as e:
        logger.warning("[vlm_judge] generator failed: %s", e)
        return 0.0
    m = _NUM_RE.search((text or "")[:120])
    if not m:
        return 0.0
    try:
        v = float(m.group(1))
        return max(0.0, min(1.0, v))
    except Exception:
        return 0.0


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    candidates_in = await _lf(query, max(top_k, 8), ctx)
    if not candidates_in:
        return []
    pipeline = ctx.pipeline
    if pipeline is None or getattr(pipeline, "generator", None) is None:
        return candidates_in[:top_k]
    corpus = (ctx.extras or {}).get("corpus") if ctx.extras else None
    if corpus is None:
        return candidates_in[:top_k]

    # Score top-N candidates concurrently (bounded to 8).
    n_score = min(8, len(candidates_in))
    pages_text: List[Tuple[Tuple[str, int], str]] = []
    for (d, p, _s) in candidates_in[:n_score]:
        ps = corpus.doc_pages(query.subset, d) or []
        text = ""
        for (pn, t) in ps:
            if pn == p:
                text = t; break
        if not text:
            text = (corpus.doc_text(query.subset, d) or "")[:1500]
        pages_text.append(((d, p), text[:1500]))

    prompts = [_PROMPT.format(query=query.query, page=t) for ((_d, _p), t) in pages_text]
    coros = [_llm_score(pipeline.generator, pr) for pr in prompts]
    scores = await asyncio.gather(*coros, return_exceptions=False)

    re_ranked = sorted(zip([k for (k, _) in pages_text], scores),
                       key=lambda kv: kv[1], reverse=True)
    if len(candidates_in) > n_score:
        # tail kept in original order, lower score
        for j, (d, p, s) in enumerate(candidates_in[n_score:]):
            re_ranked.append(((d, p), 0.0))
    return [(d, p, float(s)) for ((d, p), s) in re_ranked[:top_k]]


register(MethodMeta(
    name="closed_set_vlm_judge",
    version="1.0",
    description="VLM-as-Judge rerank: LLM scores top-N candidates 0–1, re-ranks.",
    needs=["pipeline.generator", "visdom_corpus", "fusion_head_pt"],
    uses_test_labels=False,
    run=_run,
))
