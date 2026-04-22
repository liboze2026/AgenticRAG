import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from backend.services.worker_client import WorkerClient


def _make_response(status_code: int, json_data: dict) -> httpx.Response:
    response = httpx.Response(status_code, json=json_data)
    response.request = httpx.Request("GET", "http://localhost:8001/")
    return response


@pytest.mark.asyncio
async def test_encode_documents(tmp_path):
    # encode_documents now reads images from disk and base64-encodes them,
    # so the test needs a real file on disk (any bytes will do — post is mocked).
    img_path = tmp_path / "img.png"
    img_path.write_bytes(b"\x89PNG fake bytes")

    mock_response = _make_response(200, {"embeddings": [{"document_id": "doc1", "page_number": 1, "vectors": [[0.1, 0.2]]}]})
    client = WorkerClient(host="localhost", port=8001, timeout=30)
    with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await client.encode_documents([str(img_path)])
    assert len(result) == 1
    assert result[0]["document_id"] == "doc1"


@pytest.mark.asyncio
async def test_encode_query():
    mock_response = _make_response(200, {"vectors": [[0.1, 0.2, 0.3]]})
    client = WorkerClient(host="localhost", port=8001, timeout=30)
    with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await client.encode_query("what is attention?")
    assert len(result) == 1
    assert result[0] == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_health_check():
    mock_response = _make_response(200, {"status": "ok", "model": "colpali"})
    client = WorkerClient(host="localhost", port=8001, timeout=30)
    with patch.object(client._client, "get", new_callable=AsyncMock, return_value=mock_response):
        result = await client.health()
    assert result["status"] == "ok"
