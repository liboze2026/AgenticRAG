"""Closed-set RRF: fuse closed_set_random + closed_set_titlematch.

Mainly here as a sanity test of the RRF fusion logic on closed-set lists.
Won't beat titlematch alone (random is noise), but verifies the pipeline.
"""
from __future__ import annotations

import logging
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.baseline_rrf import _rrf_fuse
from backend.sota.methods.closed_set_random import _run as _rand_run
from backend.sota.methods.closed_set_titlematch import _run as _title_run

logger = logging.getLogger(__name__)


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    a = [(d, p) for (d, p, _s) in await _title_run(query, top_k * 2, ctx)]
    b = [(d, p) for (d, p, _s) in await _rand_run(query, top_k * 2, ctx)]
    return _rrf_fuse([a, b], k=60, top_k=top_k)


register(MethodMeta(
    name="closed_set_rrf",
    version="1.0",
    description="RRF fusion of closed_set_titlematch + closed_set_random (pipeline sanity).",
    needs=[],
    uses_test_labels=False,
    run=_run,
))
