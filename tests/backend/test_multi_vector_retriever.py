import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.strategies.retrievers.multi_vector import MultiVectorRetriever


@pytest.mark.asyncio
async def test_ensure_collection_creates_when_missing():
    mock_qdrant = MagicMock()
    mock_qdrant.get_collection = AsyncMock(side_effect=Exception("not found"))
    mock_qdrant.create_collection = AsyncMock()
    retriever = MultiVectorRetriever(qdrant_client=mock_qdrant, collection_name="test", vector_size=128)
    await retriever.ensure_collection()
    mock_qdrant.create_collection.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_collection_skips_when_exists():
    mock_qdrant = MagicMock()
    mock_qdrant.get_collection = AsyncMock(return_value=MagicMock())
    mock_qdrant.create_collection = AsyncMock()
    retriever = MultiVectorRetriever(qdrant_client=mock_qdrant, collection_name="test")
    await retriever.ensure_collection()
    mock_qdrant.create_collection.assert_not_called()


@pytest.mark.asyncio
async def test_index_page():
    mock_qdrant = MagicMock()
    mock_qdrant.upsert = AsyncMock()
    retriever = MultiVectorRetriever(qdrant_client=mock_qdrant, collection_name="test")
    await retriever.index(document_id="doc1", page_number=1, vectors=[[0.1, 0.2], [0.3, 0.4]], image_path="/img/page_1.png")
    mock_qdrant.upsert.assert_called_once()


@pytest.mark.asyncio
async def test_retrieve():
    mock_qdrant = MagicMock()
    mock_point = MagicMock()
    mock_point.id = "abc123"
    mock_point.score = 0.95
    mock_point.payload = {"document_id": "doc1", "page_number": 1, "image_path": "/img/page_1.png"}
    mock_qdrant.query_points = AsyncMock(return_value=MagicMock(points=[mock_point]))
    retriever = MultiVectorRetriever(qdrant_client=mock_qdrant, collection_name="test")
    results = await retriever.retrieve([[0.1, 0.2]], top_k=3)
    assert len(results) == 1
    assert results[0].document_id == "doc1"
    assert results[0].score == 0.95


@pytest.mark.asyncio
async def test_delete():
    mock_qdrant = MagicMock()
    mock_qdrant.delete = AsyncMock()
    retriever = MultiVectorRetriever(qdrant_client=mock_qdrant, collection_name="test")
    await retriever.delete("doc1")
    mock_qdrant.delete.assert_called_once()
