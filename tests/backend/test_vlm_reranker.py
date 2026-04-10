import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.strategies.rerankers.vlm_reranker import VLMReranker, _parse_score
from backend.models.schemas import RetrievalResult, Answer


def _make_result(doc, page, score=0.0):
    return RetrievalResult(document_id=doc, page_number=page, score=score, image_path=f"/{doc}.png")


def test_parse_score_basic():
    assert _parse_score("8") == 8.0
    assert _parse_score("Score: 7.5") == 7.5
    assert _parse_score("not a number") == 0.0
    assert _parse_score("") == 0.0


@pytest.mark.asyncio
async def test_rerank_orders_by_llm_score():
    mock_gen = MagicMock()
    # First page -> 3, second -> 9, third -> 5
    responses = iter(["3", "9", "5"])
    async def fake_generate(prompt, ctx):
        return Answer(text=next(responses), sources=ctx)
    mock_gen.generate = AsyncMock(side_effect=fake_generate)

    reranker = VLMReranker(base_generator=mock_gen, max_concurrent=1)
    results = [_make_result("a", 1), _make_result("b", 1), _make_result("c", 1)]
    out = await reranker.rerank("test", results, top_k=3)
    assert out[0].document_id == "b"  # highest score
    assert out[1].document_id == "c"
    assert out[2].document_id == "a"
    assert out[0].score == 9.0


@pytest.mark.asyncio
async def test_rerank_truncates_to_top_k():
    mock_gen = MagicMock()
    async def fake_generate(prompt, ctx):
        return Answer(text="5", sources=ctx)
    mock_gen.generate = AsyncMock(side_effect=fake_generate)
    reranker = VLMReranker(base_generator=mock_gen)
    results = [_make_result(str(i), 1) for i in range(10)]
    out = await reranker.rerank("q", results, top_k=3)
    assert len(out) == 3


@pytest.mark.asyncio
async def test_rerank_handles_empty():
    reranker = VLMReranker(base_generator=MagicMock())
    out = await reranker.rerank("q", [], top_k=5)
    assert out == []
