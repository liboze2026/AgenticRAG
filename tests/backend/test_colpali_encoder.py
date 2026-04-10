import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.strategies.encoders.colpali import ColPaliEncoder
from backend.models.schemas import PageImage


@pytest.mark.asyncio
async def test_encode_documents():
    mock_client = MagicMock()
    mock_client.encode_documents = AsyncMock(return_value=[
        {"vectors": [[0.1, 0.2]]},
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


@pytest.mark.asyncio
async def test_encode_documents_batching():
    """Verify pages are split into batches of batch_size."""
    mock_client = MagicMock()
    mock_client.encode_documents = AsyncMock(side_effect=[
        [{"vectors": [[0.1]]}, {"vectors": [[0.2]]}],
        [{"vectors": [[0.3]]}],
    ])
    encoder = ColPaliEncoder(worker_client=mock_client, batch_size=2)
    pages = [
        PageImage(document_id="d", page_number=1, image_path="/a.png"),
        PageImage(document_id="d", page_number=2, image_path="/b.png"),
        PageImage(document_id="d", page_number=3, image_path="/c.png"),
    ]
    embeddings = await encoder.encode_documents(pages)
    assert len(embeddings) == 3
    assert mock_client.encode_documents.call_count == 2
    assert embeddings[2].page_number == 3


@pytest.mark.asyncio
async def test_mean_pool_reduces_to_single_vector():
    mock_client = MagicMock()
    mock_client.encode_documents = AsyncMock(return_value=[
        {"vectors": [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]},
    ])
    encoder = ColPaliEncoder(worker_client=mock_client, pool_strategy="mean")
    pages = [PageImage(document_id="d", page_number=1, image_path="/a.png")]
    embeddings = await encoder.encode_documents(pages)
    assert len(embeddings[0].vectors) == 1
    assert embeddings[0].vectors[0] == [3.0, 4.0]


@pytest.mark.asyncio
async def test_kmeans_pool_reduces_to_k_clusters():
    mock_client = MagicMock()
    mock_client.encode_documents = AsyncMock(return_value=[
        {"vectors": [[float(i), 0.0] for i in range(10)]},
    ])
    encoder = ColPaliEncoder(worker_client=mock_client, pool_strategy="kmeans", num_clusters=3)
    pages = [PageImage(document_id="d", page_number=1, image_path="/a.png")]
    embeddings = await encoder.encode_documents(pages)
    assert len(embeddings[0].vectors) == 3


@pytest.mark.asyncio
async def test_no_pool_preserves_vectors():
    mock_client = MagicMock()
    mock_client.encode_documents = AsyncMock(return_value=[
        {"vectors": [[1.0, 2.0], [3.0, 4.0]]},
    ])
    encoder = ColPaliEncoder(worker_client=mock_client)  # default pool_strategy=None
    pages = [PageImage(document_id="d", page_number=1, image_path="/a.png")]
    embeddings = await encoder.encode_documents(pages)
    assert len(embeddings[0].vectors) == 2
