"""Phase 1 — Dual-channel retrieval comparison.

Runs BM25 (sparse text) and ColPali (dense visual) side-by-side, then a
Reciprocal Rank Fusion of the two, returning all three result lists for the
frontend to compare. Optionally generates an answer from the fused channel.

The module borrows the main pipeline's query_encoder + retriever (ColPali on
the active Qdrant collection), so ColPali results are guaranteed to match
what /api/query returns. BM25 indexing is shadowed: on each request we
reconcile the BM25 index against documents on disk, which means it stays in
sync without requiring document_service changes.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import time
from typing import List, Optional

from backend.lab.schemas import ChannelResult, HybridCompareResponse
from backend.models.schemas import RetrievalResult
from backend.strategies.retrievers.bm25 import BM25Retriever
from backend.strategies.retrievers.hybrid_rrf import _rrf_fuse  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)


class LabHybridService:
    """Side-by-side BM25 vs ColPali vs RRF comparator.

    Reuses the main pipeline's encoder + retriever for the dense channel;
    maintains its own BM25 index alongside.
    """

    def __init__(
        self,
        upload_dir: str,
        documents_db_path: str,
        images_dir: str = "data/images",
        bm25_path: str = "data/cache/lab_bm25.pkl",
    ):
        self.upload_dir = upload_dir
        self.documents_db_path = documents_db_path
        self.images_dir = images_dir
        os.makedirs(os.path.dirname(bm25_path), exist_ok=True)
        self.bm25 = BM25Retriever(persist_path=bm25_path)
        # Snapshot of the (doc_id, page_number) pairs currently in BM25; used
        # to skip reindexing pages we've already seen.
        self._indexed_keys = {(d["doc_id"], d["page_number"]) for d in self.bm25._docs}
        self._sync_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # BM25 index reconciliation
    # ------------------------------------------------------------------
    async def _ensure_bm25_synced(self) -> str:
        """Scan documents.db for completed docs and feed missing pages to BM25.

        Returns a one-line note describing the index state (used in API
        response so frontend can display "BM25: 24 pages indexed").
        """
        async with self._sync_lock:
            try:
                with sqlite3.connect(self.documents_db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    rows = conn.execute(
                        "SELECT id, pdf_path, total_pages FROM documents WHERE status = 'completed'"
                    ).fetchall()
            except sqlite3.Error as e:
                logger.warning("BM25 sync — cannot read documents.db: %s", e)
                return f"BM25 索引未同步: {e}"

            added = 0
            for row in rows:
                doc_id = row["id"]
                total_pages = row["total_pages"] or 0
                pdf_path = row["pdf_path"]
                if not pdf_path or not os.path.exists(pdf_path):
                    continue
                doc_dir = os.path.join(self.images_dir, doc_id)
                for page_num in range(1, total_pages + 1):
                    if (doc_id, page_num) in self._indexed_keys:
                        continue
                    image_path = os.path.join(doc_dir, f"page_{page_num}.png")
                    try:
                        await self.bm25.index(
                            document_id=doc_id,
                            page_number=page_num,
                            vectors=[],            # ignored for BM25
                            image_path=image_path,
                            pdf_path=pdf_path,
                            layout_metadata=None,
                        )
                        self._indexed_keys.add((doc_id, page_num))
                        added += 1
                    except Exception as e:
                        logger.warning("BM25 index %s p%d failed: %s", doc_id, page_num, e)

            total = len(self._indexed_keys)
            if added > 0:
                return f"BM25 已同步 {total} 页 (新增 {added})"
            if total == 0:
                return "BM25 索引为空 — 请先上传并索引文档"
            return f"BM25 索引就绪: {total} 页"

    # ------------------------------------------------------------------
    # Per-channel retrievers
    # ------------------------------------------------------------------
    async def _bm25_channel(self, query: str, top_k: int) -> ChannelResult:
        t0 = time.perf_counter()
        try:
            results = await self.bm25.retrieve_text(query, top_k=top_k)
            return ChannelResult(
                channel="bm25",
                results=results,
                timing_ms=(time.perf_counter() - t0) * 1000,
                note="" if results else "BM25 无命中 (索引为空或问题不含关键词)",
            )
        except Exception as e:
            logger.warning("BM25 retrieve failed: %s", e)
            return ChannelResult(
                channel="bm25", results=[],
                timing_ms=(time.perf_counter() - t0) * 1000,
                note=f"BM25 检索失败: {type(e).__name__}",
            )

    async def _colpali_channel(self, pipeline, query: str, top_k: int) -> ChannelResult:
        t0 = time.perf_counter()
        try:
            vectors = await pipeline.query_encoder.encode_query(query)
            results = await pipeline.retriever.retrieve(vectors, top_k=top_k)
            return ChannelResult(
                channel="colpali",
                results=results,
                timing_ms=(time.perf_counter() - t0) * 1000,
            )
        except Exception as e:
            logger.warning("ColPali retrieve failed: %s", e)
            return ChannelResult(
                channel="colpali", results=[],
                timing_ms=(time.perf_counter() - t0) * 1000,
                note=f"ColPali 检索失败: {type(e).__name__}",
            )

    @staticmethod
    def _fuse(dense: List[RetrievalResult], sparse: List[RetrievalResult],
              top_k: int, rrf_k: int = 60) -> List[RetrievalResult]:
        return _rrf_fuse(dense, sparse, k=rrf_k, top_k=top_k)

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------
    async def compare(
        self,
        pipeline,
        query: str,
        top_k: int = 5,
        rrf_k: int = 60,
        candidates: int = 20,
    ) -> HybridCompareResponse:
        """Run all three channels and return them.

        `candidates` controls per-channel pre-fusion depth; `top_k` controls
        the user-visible truncation per channel and after fusion.
        """
        bm25_note = await self._ensure_bm25_synced()

        # Run channels concurrently — they're network-/CPU-independent
        bm25_task = asyncio.create_task(self._bm25_channel(query, candidates))
        colpali_task = asyncio.create_task(self._colpali_channel(pipeline, query, candidates))
        bm25_full, colpali_full = await asyncio.gather(bm25_task, colpali_task)

        # Truncate visible lists
        bm25_view = ChannelResult(
            channel="bm25",
            results=bm25_full.results[:top_k],
            timing_ms=bm25_full.timing_ms,
            note=bm25_full.note or bm25_note,
        )
        colpali_view = ChannelResult(
            channel="colpali",
            results=colpali_full.results[:top_k],
            timing_ms=colpali_full.timing_ms,
            note=colpali_full.note,
        )

        # RRF fusion uses full candidate lists
        t_rrf = time.perf_counter()
        fused = self._fuse(colpali_full.results, bm25_full.results, top_k=top_k, rrf_k=rrf_k)
        rrf_ms = (time.perf_counter() - t_rrf) * 1000
        rrf_view = ChannelResult(
            channel="rrf",
            results=fused,
            timing_ms=rrf_ms,
            note=f"RRF (k={rrf_k}) on {len(colpali_full.results)} dense + {len(bm25_full.results)} sparse",
        )

        return HybridCompareResponse(
            query=query,
            channels=[bm25_view, colpali_view, rrf_view],
            fused_channel="rrf",
        )

    async def generate_from_fused(self, pipeline, query: str, fused: List[RetrievalResult]) -> Optional[str]:
        """Run the main pipeline's generator on the fused result list."""
        if not fused:
            return None
        try:
            ans = await pipeline.generator.generate(query, fused)
            return ans.text
        except Exception as e:
            logger.warning("Hybrid generate failed: %s", e)
            return None
