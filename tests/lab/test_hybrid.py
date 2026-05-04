"""Unit tests for Phase 1 — Hybrid (dual-channel) compare logic.

The full LabHybridService requires a sqlite db + qdrant, so we test the
RRF fusion math directly + the pieces that don't need IO.
"""
import pytest

from backend.lab.hybrid import LabHybridService
from backend.models.schemas import RetrievalResult


def make_result(doc, page, score=0.5, image="x.png"):
    return RetrievalResult(document_id=doc, page_number=page, score=score, image_path=image)


def test_rrf_intersection_boost():
    """Pages appearing in both lists should rank above pages appearing in one."""
    dense = [make_result("d1", 1), make_result("d1", 2), make_result("d1", 3)]
    sparse = [make_result("d1", 3), make_result("d1", 4), make_result("d1", 5)]
    fused = LabHybridService._fuse(dense, sparse, top_k=5, rrf_k=60)
    # d1:3 appears in both — should be at top
    assert fused[0].document_id == "d1"
    assert fused[0].page_number == 3


def test_rrf_truncates_to_top_k():
    dense = [make_result("d1", i) for i in range(1, 11)]
    sparse = [make_result("d2", i) for i in range(1, 11)]
    fused = LabHybridService._fuse(dense, sparse, top_k=3, rrf_k=60)
    assert len(fused) == 3


def test_rrf_dedup_by_doc_page():
    dense = [make_result("d1", 1), make_result("d1", 2)]
    sparse = [make_result("d1", 1), make_result("d1", 2)]
    fused = LabHybridService._fuse(dense, sparse, top_k=5, rrf_k=60)
    keys = [(r.document_id, r.page_number) for r in fused]
    assert keys == sorted(set(keys), key=keys.index)
    assert len(fused) == 2


def test_rrf_empty_inputs():
    assert LabHybridService._fuse([], [], top_k=5, rrf_k=60) == []
    only_dense = [make_result("d1", 1)]
    assert len(LabHybridService._fuse(only_dense, [], top_k=5, rrf_k=60)) == 1
    only_sparse = [make_result("d1", 2)]
    assert len(LabHybridService._fuse([], only_sparse, top_k=5, rrf_k=60)) == 1
