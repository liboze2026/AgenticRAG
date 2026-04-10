import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock
from backend.main import create_app
from backend.services.cache import DiskCache


@pytest.mark.asyncio
async def test_cache_stats_endpoint(tmp_path):
    qc = DiskCache(path=str(tmp_path / "q"), enabled=True)
    gc = DiskCache(path=str(tmp_path / "g"), enabled=True)
    qc.set("a", "1")
    gc.set("b", "2")

    app = create_app(
        worker_client=MagicMock(),
        pipeline_manager=MagicMock(),
        document_service=MagicMock(),
        query_cache=qc,
        generation_cache=gc,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/cache/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_cache"]["entries"] == 1
    assert data["generation_cache"]["entries"] == 1


@pytest.mark.asyncio
async def test_cache_clear_endpoints(tmp_path):
    qc = DiskCache(path=str(tmp_path / "q"), enabled=True)
    qc.set("a", "1")

    app = create_app(
        worker_client=MagicMock(),
        pipeline_manager=MagicMock(),
        document_service=MagicMock(),
        query_cache=qc,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete("/api/cache/query")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 1
    assert qc.get("a") is None
