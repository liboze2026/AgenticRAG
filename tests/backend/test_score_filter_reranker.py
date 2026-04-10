import pytest
from backend.strategies.rerankers.score_filter import ScoreFilterReranker
from backend.models.schemas import RetrievalResult


@pytest.mark.asyncio
async def test_filter_below_threshold():
    reranker = ScoreFilterReranker(threshold=0.5)
    results = [
        RetrievalResult(document_id="a", page_number=1, score=0.9, image_path="/a"),
        RetrievalResult(document_id="b", page_number=1, score=0.3, image_path="/b"),
        RetrievalResult(document_id="c", page_number=1, score=0.6, image_path="/c"),
    ]
    out = await reranker.rerank("q", results, top_k=10)
    assert len(out) == 2
    assert {r.document_id for r in out} == {"a", "c"}


@pytest.mark.asyncio
async def test_truncate_to_top_k():
    reranker = ScoreFilterReranker(threshold=0.0)
    results = [
        RetrievalResult(document_id=str(i), page_number=1, score=0.9, image_path="/x") for i in range(5)
    ]
    out = await reranker.rerank("q", results, top_k=2)
    assert len(out) == 2
