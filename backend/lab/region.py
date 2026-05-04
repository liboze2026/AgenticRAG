"""Phase 4 — Region-level (layout-level) retrieval.

Maintains a separate Qdrant collection where each LayoutElement (text block,
table, figure, heading) is its own multi-vector point. Crops the parent page
image to the element bbox, sends through ColPali, indexes the result.

Indexing is on-demand: the user uploads a document via the main flow (which
indexes pages); then the lab UI offers a button "索引区域" that calls
POST /api/lab/region/index/{doc_id} to crop+encode all elements on all pages
for that one document. This keeps the heavy region-encoding work explicit
and demo-controllable.

Falls back gracefully if:
* Document has no layout metadata → 0 regions indexed, note explains
* Worker is offline → returns the indexing error, doesn't corrupt collection
* Cropped element image is too small (e.g. 1px high) → skipped
"""
from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from qdrant_client import models

from backend.lab.schemas import RegionHit, RegionResponse
from backend.models.schemas import BoundingBox, LayoutElement, PageLayout

logger = logging.getLogger(__name__)

REGION_COLLECTION_NAME = "documents_regions"
REGION_VECTOR_SIZE = 128
MIN_CROP_PX = 24       # skip elements smaller than this on either axis
# Per-page hard cap: encode + upsert must finish within this window or the
# page is logged as a failure and the loop moves on. Without it, a stuck
# tunnel transfer can pin one page for hours and starve the whole job.
PAGE_BUDGET_SEC = 90.0


class LabRegionService:
    """Crop-encode-index per-LayoutElement, plus retrieve."""

    def __init__(
        self,
        qdrant_client,
        worker_client,
        document_encoder,           # ColPaliEncoder for crops
        query_encoder,              # ColPaliEncoder for queries (same as main)
        documents_db_path: str,
        images_dir: str,
        regions_dir: str = "data/regions",
        collection_name: str = REGION_COLLECTION_NAME,
    ):
        self.qdrant = qdrant_client
        self.worker_client = worker_client
        self.document_encoder = document_encoder
        self.query_encoder = query_encoder
        self.documents_db_path = documents_db_path
        self.images_dir = images_dir
        self.regions_dir = regions_dir
        self.collection_name = collection_name
        os.makedirs(regions_dir, exist_ok=True)
        self._index_lock = asyncio.Lock()
        # Job progress tracking — keyed by doc_id (or "*" for index_all)
        self._jobs: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Job state — exposed via /api/lab/region/status/{doc_id}
    # ------------------------------------------------------------------
    def _set_job(self, doc_id: str, **fields):
        st = self._jobs.setdefault(doc_id, {
            "doc_id": doc_id, "state": "pending",
            "indexed": 0, "skipped": 0, "errors": 0,
            "current_page": 0, "total_pages": 0,
            "started_at": None, "finished_at": None, "note": "",
        })
        st.update(fields)

    def get_job(self, doc_id: str) -> Optional[Dict[str, Any]]:
        return self._jobs.get(doc_id)

    def list_jobs(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._jobs)

    # ------------------------------------------------------------------
    # Collection setup
    # ------------------------------------------------------------------
    async def ensure_collection(self) -> None:
        try:
            await self.qdrant.get_collection(self.collection_name)
        except Exception:
            await self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=REGION_VECTOR_SIZE,
                    distance=models.Distance.COSINE,
                    multivector_config=models.MultiVectorConfig(
                        comparator=models.MultiVectorComparator.MAX_SIM,
                    ),
                ),
            )
            logger.info("Created region collection %s", self.collection_name)

    async def collection_count(self) -> int:
        """Best-effort: returns 0 if collection missing or unreachable."""
        try:
            info = await self.qdrant.get_collection(self.collection_name)
            return int(getattr(info, "points_count", 0) or 0)
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Document discovery
    # ------------------------------------------------------------------
    def _completed_doc_pages(self, doc_id: Optional[str]) -> List[Tuple[str, int]]:
        """Return [(doc_id, total_pages), ...] for completed docs."""
        try:
            with sqlite3.connect(self.documents_db_path) as conn:
                conn.row_factory = sqlite3.Row
                if doc_id is not None:
                    rows = conn.execute(
                        "SELECT id, total_pages FROM documents "
                        "WHERE id = ? AND status = 'completed'",
                        (doc_id,)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT id, total_pages FROM documents WHERE status = 'completed'"
                    ).fetchall()
                return [(r["id"], r["total_pages"] or 0) for r in rows]
        except sqlite3.Error as e:
            logger.warning("region: cannot read documents.db: %s", e)
            return []

    async def _fetch_layout_via_qdrant(self, doc_id: str, page_number: int) -> Optional[PageLayout]:
        """Read PageLayout payload back from main collection (set by indexer).

        Hard 20s ceiling so a stalled tunnel cannot pin the indexer before it
        even gets to encoding. Without this, ResilientAsyncQdrantClient retries
        bury the page in 30s+ blocks of layout fetches with no progress visible.
        """
        try:
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}:{page_number}"))
            res = await asyncio.wait_for(
                self.qdrant.retrieve(
                    collection_name="documents",
                    ids=[point_id],
                    with_payload=True,
                ),
                timeout=20.0,
            )
            if not res:
                return None
            payload = res[0].payload or {}
            layout_dict = payload.get("layout")
            if not layout_dict:
                return None
            return PageLayout(**layout_dict)
        except asyncio.TimeoutError:
            logger.warning("region layout fetch TIMEOUT 20s for %s p%d", doc_id, page_number)
            return None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Cropping
    # ------------------------------------------------------------------
    @staticmethod
    def _crop_element(page_image_path: str, element: LayoutElement, page_layout: PageLayout,
                      out_path: str) -> Optional[Tuple[int, int]]:
        """Crop element bbox out of the page image; return (w, h) or None."""
        try:
            from PIL import Image
        except ImportError:
            return None
        try:
            with Image.open(page_image_path) as im:
                im_w, im_h = im.size
                # Layout bboxes are in PDF-point space scaled to image pixels by
                # processor (page_screenshot uses dpi=200, so layout coords match
                # pixel coords directly). page_width/height are in pixels.
                if page_layout.page_width <= 0 or page_layout.page_height <= 0:
                    return None
                sx = im_w / page_layout.page_width
                sy = im_h / page_layout.page_height
                x0 = max(0, int(element.bbox.x0 * sx))
                y0 = max(0, int(element.bbox.y0 * sy))
                x1 = min(im_w, int(element.bbox.x1 * sx))
                y1 = min(im_h, int(element.bbox.y1 * sy))
                w = x1 - x0
                h = y1 - y0
                if w < MIN_CROP_PX or h < MIN_CROP_PX:
                    return None
                cropped = im.crop((x0, y0, x1, y1))
                cropped.save(out_path, "PNG")
                return w, h
        except Exception as e:
            logger.warning("crop failed (%s): %s", page_image_path, e)
            return None

    # ------------------------------------------------------------------
    # Indexing one document
    # ------------------------------------------------------------------
    async def index_document(self, doc_id: str) -> Dict[str, Any]:
        """Crop + encode + upsert all regions for one document.

        Returns {indexed, skipped, errors, note} stats.
        """
        import time as _time
        from starlette.concurrency import run_in_threadpool
        await self.ensure_collection()

        async with self._index_lock:
            doc_pages = self._completed_doc_pages(doc_id)
            if not doc_pages:
                self._set_job(doc_id, state="failed", note=f"文档 {doc_id} 不存在或未完成索引")
                return {"indexed": 0, "skipped": 0, "errors": 0,
                        "note": f"文档 {doc_id} 不存在或未完成索引"}

            _, total_pages = doc_pages[0]
            doc_dir = os.path.join(self.images_dir, doc_id)
            region_doc_dir = os.path.join(self.regions_dir, doc_id)
            os.makedirs(region_doc_dir, exist_ok=True)

            self._set_job(doc_id, state="running",
                          started_at=_time.time(), total_pages=total_pages,
                          indexed=0, skipped=0, errors=0, current_page=0, note="")

            indexed = 0
            skipped = 0
            errors = 0
            for page_num in range(1, total_pages + 1):
                self._set_job(doc_id, current_page=page_num)
                page_image_path = os.path.join(doc_dir, f"page_{page_num}.png")
                if not os.path.exists(page_image_path):
                    skipped += 1
                    continue
                layout = await self._fetch_layout_via_qdrant(doc_id, page_num)
                if layout is None or not layout.elements:
                    skipped += 1
                    continue

                # Build crop list for this page — PIL operations are CPU-bound,
                # so offload to threadpool to avoid blocking the event loop
                # (frontend health polls would stall otherwise).
                crop_paths: List[str] = []
                element_meta: List[Tuple[int, LayoutElement]] = []
                for idx, el in enumerate(layout.elements):
                    out_path = os.path.join(
                        region_doc_dir, f"page_{page_num}_el_{idx}.png"
                    )
                    crop = await run_in_threadpool(
                        self._crop_element, page_image_path, el, layout, out_path,
                    )
                    if crop is None:
                        skipped += 1
                        continue
                    crop_paths.append(out_path)
                    element_meta.append((idx, el))

                if not crop_paths:
                    self._set_job(doc_id, indexed=indexed, skipped=skipped, errors=errors)
                    continue

                # Encode crops via worker (in batches handled inside encoder).
                # Hard timeout per page so a stuck tunnel can't pin the job;
                # the next page still gets a chance.
                try:
                    raw = await asyncio.wait_for(
                        self.worker_client.encode_documents(crop_paths),
                        timeout=PAGE_BUDGET_SEC,
                    )
                except asyncio.TimeoutError:
                    logger.warning("region encode TIMEOUT after %.0fs for %s p%d",
                                   PAGE_BUDGET_SEC, doc_id, page_num)
                    errors += len(crop_paths)
                    self._set_job(doc_id, indexed=indexed, skipped=skipped, errors=errors,
                                  note=f"页 {page_num} encode 超时 {PAGE_BUDGET_SEC:.0f}s — 已跳过")
                    continue
                except Exception as e:
                    logger.exception("region encode failed for %s p%d", doc_id, page_num)
                    errors += len(crop_paths)
                    self._set_job(doc_id, indexed=indexed, skipped=skipped, errors=errors)
                    continue

                # Upsert points
                points = []
                for (idx, el), enc, crop_path in zip(element_meta, raw, crop_paths):
                    vectors = enc.get("vectors") or []
                    if not vectors:
                        skipped += 1
                        continue
                    point_id = str(uuid.uuid5(
                        uuid.NAMESPACE_DNS,
                        f"region:{doc_id}:{page_num}:{idx}",
                    ))
                    payload = {
                        "document_id": doc_id,
                        "page_number": page_num,
                        "element_index": idx,
                        "element_type": el.element_type,
                        "bbox": el.bbox.model_dump(),
                        "text": (el.text or "")[:500],
                        "image_path": page_image_path,    # parent page (for thumbnail)
                        "region_image_path": crop_path,
                    }
                    points.append(models.PointStruct(id=point_id, vector=vectors, payload=payload))
                    indexed += 1
                if points:
                    try:
                        await asyncio.wait_for(
                            self.qdrant.upsert(
                                collection_name=self.collection_name, points=points,
                            ),
                            timeout=PAGE_BUDGET_SEC,
                        )
                    except asyncio.TimeoutError:
                        logger.warning("region upsert TIMEOUT after %.0fs for %s p%d",
                                       PAGE_BUDGET_SEC, doc_id, page_num)
                        errors += len(points)
                        indexed -= len(points)
                    except Exception as e:
                        logger.exception("region upsert failed for %s p%d", doc_id, page_num)
                        errors += len(points)
                        indexed -= len(points)
                # Update job snapshot at end of each page
                self._set_job(doc_id, indexed=indexed, skipped=skipped, errors=errors)

            note = f"区域索引完成: {indexed} 个区域, 跳过 {skipped}"
            if errors:
                note += f", 失败 {errors}"
            self._set_job(doc_id, state="completed",
                          finished_at=_time.time(),
                          indexed=indexed, skipped=skipped, errors=errors, note=note)
            return {
                "indexed": indexed,
                "skipped": skipped,
                "errors": errors,
                "note": note,
            }

    # ------------------------------------------------------------------
    # Indexing all documents
    # ------------------------------------------------------------------
    async def index_all(self) -> Dict[str, Any]:
        await self.ensure_collection()
        all_docs = self._completed_doc_pages(None)
        agg = {"indexed": 0, "skipped": 0, "errors": 0, "documents": 0}
        for doc_id, _ in all_docs:
            stats = await self.index_document(doc_id)
            agg["indexed"] += stats["indexed"]
            agg["skipped"] += stats["skipped"]
            agg["errors"] += stats["errors"]
            agg["documents"] += 1
        agg["note"] = (
            f"已处理 {agg['documents']} 个文档, 共索引 {agg['indexed']} 个区域 "
            f"(跳过 {agg['skipped']}, 失败 {agg['errors']})"
        )
        return agg

    # ------------------------------------------------------------------
    # Region retrieval
    # ------------------------------------------------------------------
    async def query(self, query: str, top_k: int = 8) -> RegionResponse:
        timing: Dict[str, float] = {}
        try:
            count = await self.collection_count()
            if count == 0:
                return RegionResponse(
                    query=query, hits=[], timing_ms=timing,
                    note="区域索引为空 — 请先点击 '索引区域' 按钮 (POST /api/lab/region/index)",
                )

            t0 = time.perf_counter()
            vectors = await self.query_encoder.encode_query(query)
            timing["encode_query_ms"] = (time.perf_counter() - t0) * 1000

            t1 = time.perf_counter()
            response = await self.qdrant.query_points(
                collection_name=self.collection_name,
                query=vectors,
                limit=top_k * 3,
                with_payload=True,
            )
            timing["retrieve_ms"] = (time.perf_counter() - t1) * 1000

            hits: List[RegionHit] = []
            seen: set = set()
            for pt in (response.points or []):
                payload = pt.payload or {}
                key = (payload.get("document_id"), payload.get("page_number"),
                       payload.get("element_index"))
                if key in seen:
                    continue
                seen.add(key)
                bbox_data = payload.get("bbox") or {}
                try:
                    bbox = BoundingBox(**bbox_data)
                except Exception:
                    continue
                hits.append(RegionHit(
                    document_id=payload.get("document_id", ""),
                    page_number=payload.get("page_number", 0),
                    element_index=payload.get("element_index", 0),
                    element_type=payload.get("element_type", "text_block"),
                    bbox=bbox,
                    score=float(pt.score),
                    image_path=payload.get("image_path", ""),
                    text=payload.get("text", ""),
                ))
                if len(hits) >= top_k:
                    break

            return RegionResponse(
                query=query, hits=hits, timing_ms=timing,
                note=f"区域级命中 {len(hits)}/{count} (集合总数)",
            )
        except Exception as e:
            logger.exception("region query failed")
            return RegionResponse(
                query=query, hits=[], timing_ms=timing,
                note=f"区域检索失败: {type(e).__name__}: {e}",
            )

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------
    async def delete_document(self, doc_id: str) -> int:
        """Drop all region points for one document. Returns approximate count."""
        try:
            await self.qdrant.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(must=[models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=doc_id),
                    )]),
                ),
            )
            return 1
        except Exception as e:
            logger.warning("region delete failed: %s", e)
            return 0
