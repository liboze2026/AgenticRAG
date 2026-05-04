"""Phase 5 — Lab health aggregator.

One-stop endpoint that reports the readiness of every lab feature, so the
frontend dashboard can show clear "✓ ready / ✗ blocked" indicators rather
than letting individual feature pages fail with cryptic errors.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import List

from backend.lab.gmm import is_sklearn_available
from backend.lab.schemas import LabHealth

logger = logging.getLogger(__name__)


async def collect_lab_health(
    documents_db_path: str,
    bm25_doc_count: int,
    region_service,
    main_pipeline,
) -> LabHealth:
    notes: List[str] = []

    # --- Layout readiness: scan documents.db for at least one doc with layout
    layout_ready = False
    try:
        with sqlite3.connect(documents_db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE status = 'completed'"
            ).fetchone()
            if row and row[0] > 0:
                layout_ready = True
            else:
                notes.append("未发现已索引的文档 — 请先在 [文档管理] 页上传 PDF")
    except sqlite3.Error as e:
        notes.append(f"无法读取文档数据库: {e}")

    # --- sklearn for GMM
    sklearn_available = is_sklearn_available()
    if not sklearn_available:
        notes.append("sklearn 未安装 — Phase 3 (GMM) 将退化为固定 top-k")

    # --- Region collection
    region_count = 0
    region_ready = False
    if region_service is not None:
        region_count = await region_service.collection_count()
        region_ready = region_count > 0
        if not region_ready:
            notes.append(
                "区域级索引为空 — 请在 [区域级检索] 页点击 '索引所有文档区域'"
            )

    # --- Main pipeline
    main_ok = main_pipeline is not None and main_pipeline.retriever is not None
    if not main_ok:
        notes.append("主 pipeline 未就绪 — 检查 Qdrant 与 Worker 是否在线")

    # --- BM25 readiness
    if bm25_doc_count == 0:
        notes.append("BM25 索引为空 — 在 [双通道融合] 页发起首次查询会自动同步")

    return LabHealth(
        bm25_ready=bm25_doc_count > 0,
        bm25_doc_count=bm25_doc_count,
        layout_ready=layout_ready,
        sklearn_available=sklearn_available,
        region_collection_ready=region_ready,
        region_point_count=region_count,
        main_pipeline_ok=main_ok,
        notes=notes,
    )
