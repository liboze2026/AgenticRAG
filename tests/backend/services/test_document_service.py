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


@pytest.mark.asyncio
async def test_filter_by_dataset(doc_service):
    a = await doc_service.upload(filename="a.pdf", content=b"a", dataset_id=1)
    b = await doc_service.upload(filename="b.pdf", content=b"b", dataset_id=2)
    c = await doc_service.upload(filename="c.pdf", content=b"c", dataset_id=1)

    list1 = doc_service.list_documents(dataset_id=1)
    assert {d.id for d in list1} == {a.id, c.id}

    list2 = doc_service.list_documents(dataset_id=2)
    assert {d.id for d in list2} == {b.id}

    counts = doc_service.count_by_dataset()
    assert counts == {1: 2, 2: 1}


@pytest.mark.asyncio
async def test_recover_orphaned(doc_service):
    a = await doc_service.upload(filename="a.pdf", content=b"a")
    b = await doc_service.upload(filename="b.pdf", content=b"b")
    # Manually mark them as 'indexing' to simulate a crash
    with doc_service._connect() as conn:
        conn.execute("UPDATE documents SET status='indexing'")
        conn.commit()

    recovered = doc_service.recover_orphaned()
    assert set(recovered) == {a.id, b.id}
    for doc_id in recovered:
        assert doc_service.get_document(doc_id).status == "failed"


@pytest.mark.asyncio
async def test_recover_orphaned_empty(doc_service):
    await doc_service.upload(filename="a.pdf", content=b"a")
    # No 'indexing' rows present
    recovered = doc_service.recover_orphaned()
    assert recovered == []


@pytest.mark.asyncio
async def test_persistence_across_instances(tmp_path):
    mock_pipeline = MagicMock()
    mock_pipeline.retriever = MagicMock()
    mock_pipeline.retriever.delete = AsyncMock()
    upload_dir = str(tmp_path / "uploads")

    svc1 = DocumentService(upload_dir=upload_dir, pipeline=mock_pipeline)
    info = await svc1.upload(filename="persistent.pdf", content=b"data")

    svc2 = DocumentService(upload_dir=upload_dir, pipeline=mock_pipeline)
    docs = svc2.list_documents()
    assert len(docs) == 1
    assert docs[0].id == info.id
    assert docs[0].filename == "persistent.pdf"
