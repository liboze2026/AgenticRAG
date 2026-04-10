import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.strategies.retrievers.hybrid_rrf import HybridRRFRetriever, _rrf_fuse
from backend.models.schemas import RetrievalResult


def _r(doc, page, score):
    return RetrievalResult(document_id=doc, page_number=page, score=score, image_path=f"/{doc}.png")


def test_rrf_fuse_combines_ranks():
    dense = [_r("a", 1, 0.9), _r("b", 1, 0.8), _r("c", 1, 0.7)]
    sparse = [_r("c", 1, 5.0), _r("a", 1, 4.0), _r("d", 1, 3.0)]
    fused = _rrf_fuse(dense, sparse, k=60, top_k=3)
    assert len(fused) == 3
    fused_ids = {r.document_id for r in fused}
    # 'a' and 'c' appear in both -> should rank highest
    assert "a" in fused_ids
    assert "c" in fused_ids


@pytest.mark.asyncio
async def test_hybrid_retrieve_calls_both():
    dense = MagicMock()
    dense.retrieve = AsyncMock(return_value=[_r("a", 1, 0.9)])
    sparse = MagicMock()
    sparse.retrieve_text = AsyncMock(return_value=[_r("b", 1, 5.0)])

    hybrid = HybridRRFRetriever(dense_retriever=dense, sparse_retriever=sparse, candidates=10)
    hybrid.set_query("test query")
    results = await hybrid.retrieve([[0.1]], top_k=5)
    dense.retrieve.assert_called_once()
    sparse.retrieve_text.assert_called_once_with("test query", top_k=10)
    assert len(results) == 2
