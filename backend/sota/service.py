"""SOTA bundle: held on app.state.sota_bundle. Constructed once at startup."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from backend.sota.executor import RunExecutor
from backend.sota.indexers import BaseIndexer, Bm25LabIndexer, ColPaliMainIndexer
from backend.sota.runs import RunRegistry

# Importing methods/__init__ triggers method registration as a side effect.
from backend.sota import methods as _methods_pkg  # noqa: F401

logger = logging.getLogger(__name__)


@dataclass
class SotaBundle:
    registry: RunRegistry
    executor: RunExecutor
    indexers: Dict[str, BaseIndexer]
    sota_data_root: str

    def get_indexer(self, name: str) -> Optional[BaseIndexer]:
        return self.indexers.get(name)


def build_sota_bundle(
    sota_data_root: str,
    runs_root: str,
    pipeline,
    lab_bundle,
    qdrant_client,
    worker_client,
    collection_name: str = "documents",
) -> SotaBundle:
    registry = RunRegistry(root=runs_root)
    executor = RunExecutor(
        registry=registry, sota_data_root=sota_data_root,
        pipeline=pipeline, lab_bundle=lab_bundle,
        qdrant_client=qdrant_client, worker_client=worker_client,
    )
    indexers: Dict[str, BaseIndexer] = {}
    if qdrant_client is not None:
        indexers["colpali_main"] = ColPaliMainIndexer(qdrant_client, collection_name)
    if lab_bundle is not None:
        indexers["bm25_lab"] = Bm25LabIndexer(lab_bundle)
    logger.info(
        "[sota] bundle ready: %d indexers, runs at %s",
        len(indexers), runs_root,
    )
    return SotaBundle(
        registry=registry, executor=executor, indexers=indexers,
        sota_data_root=sota_data_root,
    )
