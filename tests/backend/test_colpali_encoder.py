import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.strategies.encoders.colpali import ColPaliEncoder
from backend.models.schemas import PageImage


@pytest.mark.asyncio
async def test_encode_documents():
    mock_client = MagicMock()
    mock_client.encode_documents = AsyncMock(return_value=[
        {"document_id": "doc1", "page_number": 1, "vectors": [[0.1, 0.2]]},
    ])
    encoder = ColPaliEncoder(worker_client=mock_client)
    pages = [PageImage(document_id="doc1", page_number=1, image_path="/img/page_1.png")]
    embeddings = await encoder.encode_documents(pages)
    assert len(embeddings) == 1
    assert embeddings[0].document_id == "doc1"
    assert embeddings[0].vectors == [[0.1, 0.2]]


@pytest.mark.asyncio
async def test_encode_query():
    mock_client = MagicMock()
    mock_client.encode_query = AsyncMock(return_value=[[0.3, 0.4]])
    encoder = ColPaliEncoder(worker_client=mock_client)
    vectors = await encoder.encode_query("what is attention?")
    assert vectors == [[0.3, 0.4]]
