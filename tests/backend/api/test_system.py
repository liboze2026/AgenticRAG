import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from backend.main import create_app


@pytest.mark.asyncio
async def test_health():
    mock_worker = MagicMock()
    mock_worker.health = AsyncMock(return_value={"status": "ok", "model": "colpali"})
    mock_qdrant = MagicMock()
    mock_qdrant.get_collections = AsyncMock(return_value=MagicMock())
    app = create_app(
        worker_client=mock_worker,
        pipeline_manager=MagicMock(),
        document_service=MagicMock(),
        qdrant_client=mock_qdrant,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["worker"]["status"] == "ok"
    assert resp.json()["qdrant"]["status"] == "ok"
