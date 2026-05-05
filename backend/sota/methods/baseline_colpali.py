"""ColPali baseline: delegate to main pipeline's query encoder + retriever."""
from __future__ import annotations

import logging
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register

logger = logging.getLogger(__name__)


async def _run(query: str, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    pipeline = ctx.pipeline
    if pipeline is None or pipeline.query_encoder is None or pipeline.retriever is None:
        raise RuntimeError("main pipeline / ColPali retriever unavailable")
    vectors = await pipeline.query_encoder.encode_query(query)
    hits = await pipeline.retriever.retrieve(vectors, top_k=top_k)
    return [(h.document_id, h.page_number, float(h.score)) for h in hits]


register(MethodMeta(
    name="baseline_colpali",
    version="1.0",
    description="Main-pipeline ColPali multi-vector retrieval (page-level).",
    needs=["pipeline"],
    uses_test_labels=False,
    run=_run,
))
