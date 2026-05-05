"""Method registry: name → MethodMeta. Loaded lazily on first import.

Academic-integrity rule: a method cannot expose `uses_test_labels=True`.
The loader rejects any module that does.

Method signature:
    async def run(query: SotaQuery, top_k: int, ctx: MethodContext)
        -> List[Tuple[doc_id, page_number, score]]

Methods can either:
* operate corpus-wide (using main pipeline / Qdrant), e.g. `baseline_colpali`
* operate closed-set within `query.metadata['candidate_docs']`, e.g. all
  `closed_set_*` methods. Closed-set is the methodology used by the
  VisDoMBench paper (Suri et al. 2025).
"""
from __future__ import annotations

import dataclasses
import logging
from typing import Awaitable, Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)

PageKey = Tuple[str, int]


@dataclasses.dataclass
class MethodContext:
    """Everything a method needs to run a query, injected by the executor."""
    pipeline: object
    lab_bundle: object
    qdrant_client: object
    worker_client: object
    cancelled_flag: Callable[[], bool] = lambda: False
    extras: Dict = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class MethodMeta:
    name: str
    version: str
    description: str
    needs: List[str]
    uses_test_labels: bool
    run: Callable[..., Awaitable[List[Tuple[str, int, float]]]]


METHOD_REGISTRY: Dict[str, MethodMeta] = {}


def register(meta: MethodMeta) -> None:
    if meta.uses_test_labels:
        raise RuntimeError(
            f"academic integrity violation: method {meta.name!r} flags "
            f"uses_test_labels=True; methods must never see test labels"
        )
    METHOD_REGISTRY[meta.name] = meta
    logger.info("[sota] registered method %s v%s", meta.name, meta.version)


def get_method(name: str) -> MethodMeta:
    if name not in METHOD_REGISTRY:
        raise KeyError(f"method not registered: {name}")
    return METHOD_REGISTRY[name]


# Eager import — registers each method at module load.
from . import baseline_colpali, baseline_bm25, baseline_rrf  # noqa: E402,F401
from . import closed_set_random, closed_set_titlematch, closed_set_rrf  # noqa: E402,F401
from . import closed_set_bm25_text, closed_set_bm25_page  # noqa: E402,F401
from . import closed_set_dense  # noqa: E402,F401
from . import closed_set_hybrid, closed_set_hyde  # noqa: E402,F401
from . import closed_set_ensemble  # noqa: E402,F401
from . import closed_set_cross_rerank  # noqa: E402,F401
from . import closed_set_text_rrf  # noqa: E402,F401
from . import closed_set_clip  # noqa: E402,F401
from . import closed_set_learned_fusion  # noqa: E402,F401
from . import closed_set_vlm_judge  # noqa: E402,F401
from . import closed_set_router  # noqa: E402,F401
from . import closed_set_graph  # noqa: E402,F401
from . import closed_set_colpali  # noqa: E402,F401
from . import closed_set_xmi_cal  # noqa: E402,F401
from . import closed_set_csc_eig  # noqa: E402,F401
from . import closed_set_cdpr  # noqa: E402,F401
from . import closed_set_sqr  # noqa: E402,F401
from . import closed_set_escape  # noqa: E402,F401
from . import closed_set_taf  # noqa: E402,F401
from . import closed_set_ses  # noqa: E402,F401
from . import closed_set_nirr  # noqa: E402,F401
from . import closed_set_ascend  # noqa: E402,F401
from . import closed_set_pcbr  # noqa: E402,F401
from . import closed_set_ccc  # noqa: E402,F401
from . import closed_set_wdpr  # noqa: E402,F401
