import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.services.document_service import DocumentService
from backend.models.schemas import PageImage


@pytest.fixture
def doc_service(tmp_path):
    mock_pipeline = MagicMock()
    mock_pipeline.index_document = AsyncMock(return_value=[
        PageImage(document_id="doc1", page_number=1, image_path="/img/p1.png"),
    ])
    mock_pipeline.retriever = MagicMock()
    mock_pipeline.retriever.delete = AsyncMock()
    return DocumentService(upload_dir=str(tmp_path / "uploads"), pipeline=mock_pipeline)


@pytest.mark.asyncio
async def test_upload_and_list(doc_service):
    doc_info = await doc_service.upload(filename="test.pdf", content=b"%PDF-1.4 fake")
    assert doc_info.filename == "test.pdf"
    assert doc_info.status == "pending"
    docs = doc_service.list_documents()
    assert len(docs) == 1
    assert docs[0].id == doc_info.id


@pytest.mark.asyncio
async def test_index_document(doc_service):
    doc_info = await doc_service.upload(filename="test.pdf", content=b"%PDF fake")
    await doc_service.index_document(doc_info.id)
    updated = doc_service.get_document(doc_info.id)
    assert updated.status == "completed"


@pytest.mark.asyncio
async def test_delete_document(doc_service):
    doc_info = await doc_service.upload(filename="test.pdf", content=b"%PDF fake")
    await doc_service.delete_document(doc_info.id)
    assert doc_service.get_document(doc_info.id) is None


def test_get_nonexistent(doc_service):
    assert doc_service.get_document("nonexistent") is None
