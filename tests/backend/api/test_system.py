import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from backend.main import create_app


@pytest.mark.asyncio
async def test_health():
    mock_worker = MagicMock()
    mock_worker.health = AsyncMock(return_value={"status": "ok", "model": "colpali"})
    app = create_app(worker_client=mock_worker, pipeline_manager=MagicMock(), document_service=MagicMock())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["worker"]["status"] == "ok"
