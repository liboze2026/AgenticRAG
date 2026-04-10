import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock
from worker.main import create_worker_app


@pytest.fixture
def mock_model_manager():
    manager = MagicMock()
    manager.encode_images.return_value = [{"vectors": [[0.1, 0.2, 0.3]]}]
    manager.encode_query.return_value = [[0.4, 0.5, 0.6]]
    manager.model_name.return_value = "colpali-v1.2"
    return manager


@pytest.mark.asyncio
async def test_encode_query(mock_model_manager):
    app = create_worker_app(model_manager=mock_model_manager)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/encode/query", json={"query": "what is attention?"})
    assert resp.status_code == 200
    assert resp.json()["vectors"] == [[0.4, 0.5, 0.6]]


@pytest.mark.asyncio
async def test_encode_documents(mock_model_manager):
    app = create_worker_app(model_manager=mock_model_manager)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/encode/documents", json={"image_paths": ["/fake/img.png"]})
    assert resp.status_code == 200
    assert len(resp.json()["embeddings"]) == 1


@pytest.mark.asyncio
async def test_worker_health(mock_model_manager):
    app = create_worker_app(model_manager=mock_model_manager)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert "model" in resp.json()
