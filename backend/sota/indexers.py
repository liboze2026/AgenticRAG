"""Indexer facade. Phase 0 wraps existing main-pipeline + lab/hybrid services.

Phase 1 will add ColQwen2.5, jina-clip-v2, DSE — each as a new BaseIndexer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class IndexHealth:
    encoder: str
    subset: Optional[str]
    ok: bool
    message: str
    points: Optional[int] = None


class BaseIndexer:
    name: str = "base"

    async def health(self, subset: Optional[str] = None) -> IndexHealth:
        return IndexHealth(encoder=self.name, subset=subset, ok=False, message="not implemented")


class ColPaliMainIndexer(BaseIndexer):
    """Phase 0 wrapper around the main 'documents' Qdrant collection."""
    name = "colpali_main"

    def __init__(self, qdrant_client, collection_name: str = "documents"):
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name

    async def health(self, subset: Optional[str] = None) -> IndexHealth:
        try:
            info = await self.qdrant_client.get_collection(self.collection_name)
            n = getattr(info, "points_count", 0) or 0
            return IndexHealth(
                encoder=self.name, subset=subset, ok=True,
                message=f"{n} points in {self.collection_name}", points=n,
            )
        except Exception as e:
            return IndexHealth(
                encoder=self.name, subset=subset, ok=False,
                message=f"{type(e).__name__}: {e}",
            )


class Bm25LabIndexer(BaseIndexer):
    """Phase 0 wrapper around lab/hybrid BM25 index."""
    name = "bm25_lab"

    def __init__(self, lab_bundle):
        self.lab_bundle = lab_bundle

    async def health(self, subset: Optional[str] = None) -> IndexHealth:
        try:
            if self.lab_bundle is None or self.lab_bundle.hybrid is None:
                return IndexHealth(
                    encoder=self.name, subset=subset,
                    ok=False, message="lab.hybrid unavailable",
                )
            n = len(getattr(self.lab_bundle.hybrid, "_indexed_keys", set()))
            return IndexHealth(
                encoder=self.name, subset=subset, ok=True,
                message=f"{n} BM25 page records", points=n,
            )
        except Exception as e:
            return IndexHealth(
                encoder=self.name, subset=subset, ok=False,
                message=f"{type(e).__name__}: {e}",
            )
