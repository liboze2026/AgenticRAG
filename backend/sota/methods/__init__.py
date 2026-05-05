"""Method registry: name → MethodMeta. Loaded lazily on first import.

Academic-integrity rule: a method cannot expose `uses_test_labels=True`.
The loader rejects any module that does.
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
