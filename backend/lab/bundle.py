"""Lab bundle — single struct holding lab-side services for app.state.lab_bundle.

Constructed once at startup in run.py, shared by all /api/lab/* handlers.
Stays decoupled from main pipeline_manager: lab feature crashes can never
take down the main /api/query path.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from backend.lab.hybrid import LabHybridService
from backend.lab.region import LabRegionService

logger = logging.getLogger(__name__)


@dataclass
class LabBundle:
    """All lab-side services. Any field can be None when its preconditions
    aren't met (e.g. region service can't initialize without a worker)."""
    hybrid: LabHybridService
    region: Optional[LabRegionService]
    documents_db_path: str


def build_lab_bundle(
    upload_dir: str,
    documents_db_path: str,
    images_dir: str,
    qdrant_client,
    worker_client,
    pipeline,
) -> LabBundle:
    """Construct the lab bundle. Best-effort: returns a partial bundle if
    region indexing isn't possible (no encoder, etc.)."""
    hybrid = LabHybridService(
        upload_dir=upload_dir,
        documents_db_path=documents_db_path,
        images_dir=images_dir,
    )

    region: Optional[LabRegionService] = None
    try:
        if pipeline is not None and pipeline.document_encoder is not None:
            region = LabRegionService(
                qdrant_client=qdrant_client,
                worker_client=worker_client,
                document_encoder=pipeline.document_encoder,
                query_encoder=pipeline.query_encoder,
                documents_db_path=documents_db_path,
                images_dir=images_dir,
            )
    except Exception:
        logger.exception("lab region service init failed — region features disabled")

    return LabBundle(
        hybrid=hybrid,
        region=region,
        documents_db_path=documents_db_path,
    )
