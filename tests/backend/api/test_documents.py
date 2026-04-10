import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from backend.main import create_app
from backend.models.schemas import DocumentInfo


@pytest.fixture
def mock_deps():
    doc = DocumentInfo(id="abc", filename="test.pdf", total_pages=0, status="pending")
    mock_doc_service = MagicMock()
    mock_doc_service.upload = AsyncMock(return_value=doc)
    mock_doc_service.list_documents.return_value = [doc]
    mock_doc_service.get_document.return_value = doc
    mock_doc_service.index_document = AsyncMock()
    mock_doc_service.delete_document = AsyncMock()
    return {"worker_client": MagicMock(), "pipeline_manager": MagicMock(), "document_service": mock_doc_service}


@pytest.mark.asyncio
async def test_upload_document(mock_deps):
    app = create_app(**mock_deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/documents/upload", files={"file": ("test.pdf", b"fake pdf", "application/pdf")})
    assert resp.status_code == 200
    assert resp.json()["filename"] == "test.pdf"


@pytest.mark.asyncio
async def test_list_documents(mock_deps):
    app = create_app(**mock_deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/documents")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_document(mock_deps):
    app = create_app(**mock_deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete("/api/documents/abc")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_retry_failed_document():
    doc = DocumentInfo(id="abc", filename="test.pdf", total_pages=0, status="failed")
    mock_doc_service = MagicMock()
    mock_doc_service.get_document.return_value = doc
    mock_doc_service.index_document = AsyncMock()
    deps = {"worker_client": MagicMock(), "pipeline_manager": MagicMock(), "document_service": mock_doc_service}
    app = create_app(**deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/documents/abc/retry")
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_retry_completed_document_fails():
    doc = DocumentInfo(id="abc", filename="test.pdf", total_pages=5, status="completed")
    mock_doc_service = MagicMock()
    mock_doc_service.get_document.return_value = doc
    deps = {"worker_client": MagicMock(), "pipeline_manager": MagicMock(), "document_service": mock_doc_service}
    app = create_app(**deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/documents/abc/retry")
    assert resp.status_code == 400
