"""Shared in-memory PageLayout cache.

Phase 4 (region) and Phase 6 (graph) both repeatedly fetch the same
PageLayout payloads from the main `documents` collection. On a stable
demo dataset this is wasteful: layouts only change when a document is
re-indexed.

This module owns a process-wide async cache:

* `fetch(doc_id, page)` — cached read with a 10s timeout fallback
* `preload(doc_id, total_pages)` — bulk warmup via Qdrant scroll/retrieve
* `invalidate(doc_id)` — drop entries for one document on re-index
* `count()` — diagnostic for /api/lab/health

Misses fall through to a single Qdrant `retrieve` call. A sentinel
`_NEGATIVE` is stored for known-missing pages so we don't slam Qdrant
repeatedly on a doc that legitimately has no layout payload.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Dict, Optional, Tuple

from backend.models.schemas import PageLayout

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT_SEC = 10.0
_NEGATIVE = object()  # sentinel for known-missing layout


class LayoutCache:
    """Process-wide PageLayout cache shared by graph + region services."""

    def __init__(self, qdrant_client, collection_name: str = "documents"):
        self.qdrant = qdrant_client
        self.collection_name = collection_name
        self._cache: Dict[Tuple[str, int], object] = {}
        self._inflight: Dict[Tuple[str, int], asyncio.Future] = {}
        self._lock = asyncio.Lock()

    def count(self) -> int:
        return sum(1 for v in self._cache.values() if v is not _NEGATIVE)

    def invalidate(self, doc_id: str) -> int:
        keys = [k for k in self._cache if k[0] == doc_id]
        for k in keys:
            self._cache.pop(k, None)
        return len(keys)

    async def fetch(self, doc_id: str, page: int) -> Optional[PageLayout]:
        key = (doc_id, page)
        cached = self._cache.get(key)
        if cached is _NEGATIVE:
            return None
        if cached is not None:
            return cached  # type: ignore[return-value]

        # Coalesce concurrent fetches for the same key — only one Qdrant
        # request per (doc_id, page) is in flight at a time.
        async with self._lock:
            cached = self._cache.get(key)
            if cached is _NEGATIVE:
                return None
            if cached is not None:
                return cached  # type: ignore[return-value]
            existing = self._inflight.get(key)
            if existing is None:
                fut: asyncio.Future = asyncio.get_running_loop().create_future()
                self._inflight[key] = fut
                asyncio.create_task(self._fetch_one(key, fut))
                existing = fut
        return await existing

    async def _fetch_one(self, key: Tuple[str, int], fut: asyncio.Future) -> None:
        doc_id, page = key
        try:
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}:{page}"))
            res = await asyncio.wait_for(
                self.qdrant.retrieve(
                    collection_name=self.collection_name,
                    ids=[point_id],
                    with_payload=True,
                ),
                timeout=_FETCH_TIMEOUT_SEC,
            )
            payload = (res[0].payload or {}) if res else {}
            ld = payload.get("layout")
            layout = PageLayout(**ld) if ld else None
            self._cache[key] = layout if layout is not None else _NEGATIVE
            if not fut.done():
                fut.set_result(layout)
        except asyncio.TimeoutError:
            logger.warning("layout cache TIMEOUT for %s p%d", doc_id, page)
            if not fut.done():
                fut.set_result(None)
        except Exception:
            logger.exception("layout cache fetch failed for %s p%d", doc_id, page)
            if not fut.done():
                fut.set_result(None)
        finally:
            self._inflight.pop(key, None)

    async def preload(self, doc_id: str, total_pages: int) -> int:
        """Warm the cache for one whole document. Returns the number of
        layouts that were actually loaded (vs already cached / missing).
        Errors are tolerated per page so one bad doc never blocks others.
        """
        if total_pages <= 0:
            return 0
        # Bulk-fetch all pages in parallel — bounded by Qdrant client
        # concurrency. _fetch_one populates self._cache as a side effect.
        async def _go(page: int):
            await self.fetch(doc_id, page)

        tasks = [_go(p) for p in range(1, total_pages + 1)
                 if (doc_id, p) not in self._cache]
        if not tasks:
            return 0
        await asyncio.gather(*tasks, return_exceptions=True)
        return sum(1 for p in range(1, total_pages + 1)
                   if self._cache.get((doc_id, p)) not in (None, _NEGATIVE))
