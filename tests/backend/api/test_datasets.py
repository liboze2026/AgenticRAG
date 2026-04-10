import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock
from backend.main import create_app
from backend.services.dataset_service import DatasetService
from backend.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_create_list_delete_dataset(tmp_path):
    ds_svc = DatasetService(db_path=str(tmp_path / "ds.db"))
    mock_pipeline = MagicMock()
    mock_pipeline.retriever = MagicMock()
    doc_svc = DocumentService(upload_dir=str(tmp_path / "uploads"), pipeline=mock_pipeline)

    app = create_app(
        worker_client=MagicMock(),
        pipeline_manager=MagicMock(),
        document_service=doc_svc,
        dataset_service=ds_svc,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create
        resp = await client.post("/api/datasets", json={"name": "exp1", "description": "first"})
        assert resp.status_code == 200
        ds_id = resp.json()["id"]

        # List
        resp = await client.get("/api/datasets")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        # Duplicate name
        resp = await client.post("/api/datasets", json={"name": "exp1"})
        assert resp.status_code == 400

        # Delete
        resp = await client.delete(f"/api/datasets/{ds_id}")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_upload_with_dataset_id(tmp_path):
    ds_svc = DatasetService(db_path=str(tmp_path / "ds.db"))
    mock_pipeline = MagicMock()
    mock_pipeline.retriever = MagicMock()
    mock_pipeline.index_document = AsyncMock(return_value=[])
    doc_svc = DocumentService(upload_dir=str(tmp_path / "uploads"), pipeline=mock_pipeline)

    ds = ds_svc.create("d1")

    app = create_app(
        worker_client=MagicMock(),
        pipeline_manager=MagicMock(),
        document_service=doc_svc,
        dataset_service=ds_svc,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/documents/upload?dataset_id={ds.id}",
            files={"file": ("test.pdf", b"%PDF fake", "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["dataset_id"] == ds.id

        # List filtered by dataset
        resp = await client.get(f"/api/documents?dataset_id={ds.id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
