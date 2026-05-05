"""Closed-set HyDE (Hypothetical Document Embeddings).

Pipeline:
  1. LLM generates a hypothetical answer paragraph for the query
  2. Encode that hypothetical doc with bge-base
  3. Rank candidate pages by cosine similarity to the hypothetical doc
  4. Optionally fuse with raw query embedding (here: just hypothetical)

Generator priority: zhipu (cheap, fast) → openai → anthropic. If all fail,
falls back to plain dense retrieval.

Reference: Gao et al., "Precise Zero-Shot Dense Retrieval without Relevance
Labels" (ACL 2023). Reliably +2-5 pt R@1 over q→d cosine on out-of-domain
benchmarks.
"""
from __future__ import annotations

import logging
import os
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.closed_set_dense import (
    _load_query_encoder, _load_subset_index,
)

logger = logging.getLogger(__name__)


_HYDE_SYSTEM = (
    "You are a helpful assistant. Given a question, write a short, "
    "factual paragraph (~3-5 sentences) that answers it as if quoted "
    "from a reference document. Do not refuse; just write the paragraph."
)


async def _generate_hypothetical(query_text: str, ctx: MethodContext) -> str:
    """Best-effort LLM call. Returns the original query if no generator works."""
    pipeline = ctx.pipeline
    if pipeline is None or pipeline.generator is None:
        return query_text
    gen = pipeline.generator
    # Generators in this codebase have heterogeneous interfaces. Try a
    # narrow text completion path; on any failure just return the query.
    prompt = f"{_HYDE_SYSTEM}\n\nQuestion: {query_text}\n\nAnswer:"
    try:
        if hasattr(gen, "generate_text"):
            return await gen.generate_text(prompt, max_tokens=200)
        # Fall back to a fake retrieval-result list of one node
        from backend.models.schemas import RetrievalResult
        fake = [RetrievalResult(
            document_id="_hyde_seed", page_number=1, score=1.0,
            image_path="", layout=None,
        )]
        ans = await gen.generate(prompt, fake)
        text = getattr(ans, "text", None) or getattr(ans, "answer", None) or str(ans)
        return text or query_text
    except Exception as e:
        logger.warning("[hyde] generator failed: %s — falling back to query", e)
        return query_text


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    candidates = (query.metadata or {}).get("candidate_docs", []) or []
    if not candidates:
        return []
    encoder = _load_query_encoder()
    if not encoder:
        from backend.sota.methods.closed_set_dense import _run as _d
        return await _d(query, top_k, ctx)
    idx = _load_subset_index(query.subset)
    if idx is None:
        from backend.sota.methods.closed_set_dense import _run as _d
        return await _d(query, top_k, ctx)

    embs, keys = idx
    try:
        import numpy as np
    except ImportError:
        return []

    hypo = await _generate_hypothetical(query.query, ctx)
    hyde_text = hypo if hypo and hypo.strip() else query.query
    cand_set = set(candidates)
    mask = np.array([k[0] in cand_set for k in keys])
    if not mask.any():
        return []
    cand_embs = embs[mask]
    cand_keys = [k for k, m in zip(keys, mask) if m]

    h_vec = encoder.encode([hyde_text], normalize_embeddings=True,
                           show_progress_bar=False)[0]
    q_vec = encoder.encode(["query: " + query.query], normalize_embeddings=True,
                           show_progress_bar=False)[0]
    # Mix hypothetical + raw query (50/50). Pure HyDE can drift; keeping
    # raw-query weight stabilizes scores on subsets the LLM is unfamiliar with.
    mixed = 0.5 * h_vec + 0.5 * q_vec
    mixed = mixed / (np.linalg.norm(mixed) + 1e-9)
    sims = cand_embs @ mixed
    order = sims.argsort()[::-1][:top_k]
    return [(cand_keys[i][0], cand_keys[i][1], float(sims[i])) for i in order]


register(MethodMeta(
    name="closed_set_hyde",
    version="1.0",
    description="HyDE: LLM-generated hypothetical doc + dense retrieval, mixed with raw query.",
    needs=["visdom_corpus", "dense_index", "pipeline.generator"],
    uses_test_labels=False,
    run=_run,
))
