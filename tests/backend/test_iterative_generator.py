import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.strategies.generators.iterative import (
    IterativeGenerator, _parse_confidence, _parse_need_info, _strip_metadata,
)
from backend.models.schemas import Answer, RetrievalResult


def _ctx():
    return [RetrievalResult(document_id="a", page_number=1, score=0.9, image_path="/a.png")]


def test_parse_confidence():
    assert _parse_confidence("Answer here\nCONFIDENCE: 0.85") == 0.85
    assert _parse_confidence("CONFIDENCE: 1") == 1.0
    assert _parse_confidence("no confidence here") == 0.0


def test_parse_need_info():
    assert _parse_need_info("CONFIDENCE: 0.4\nNEED_INFO: what is X?") == "what is X?"
    assert _parse_need_info("just an answer") is None


def test_strip_metadata():
    text = "The answer is 42.\nCONFIDENCE: 0.9\nNEED_INFO: extra"
    assert _strip_metadata(text) == "The answer is 42."


@pytest.mark.asyncio
async def test_single_iteration_when_confident():
    base = MagicMock()
    base.generate = AsyncMock(return_value=Answer(
        text="The answer is 42.\nCONFIDENCE: 0.9", sources=_ctx(),
    ))
    gen = IterativeGenerator(base_generator=base, max_iterations=3, confidence_threshold=0.7)
    answer = await gen.generate("test", _ctx())
    assert answer.text == "The answer is 42."
    assert base.generate.call_count == 1


@pytest.mark.asyncio
async def test_iterates_when_low_confidence():
    base = MagicMock()
    responses = iter([
        Answer(text="Maybe X?\nCONFIDENCE: 0.3\nNEED_INFO: what about Y?", sources=_ctx()),
        Answer(text="The answer is Y\nCONFIDENCE: 0.9", sources=_ctx()),
    ])
    async def fake_gen(prompt, ctx):
        return next(responses)
    base.generate = AsyncMock(side_effect=fake_gen)

    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(return_value=[
        RetrievalResult(document_id="b", page_number=1, score=0.8, image_path="/b.png"),
    ])
    mock_encoder = MagicMock()
    mock_encoder.encode_query = AsyncMock(return_value=[[0.1]])

    gen = IterativeGenerator(
        base_generator=base,
        iterative_retriever=mock_retriever,
        iterative_query_encoder=mock_encoder,
        max_iterations=3,
        confidence_threshold=0.7,
    )
    answer = await gen.generate("test", _ctx())
    assert "Y" in answer.text
    assert base.generate.call_count == 2
    assert mock_retriever.retrieve.called
    assert len(answer.sources) == 2  # original + retrieved
