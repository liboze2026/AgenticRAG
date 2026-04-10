import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from backend.main import create_app
from backend.models.schemas import RetrievalResult


@pytest.mark.asyncio
async def test_evaluate_records_experiment(tmp_path):
    from backend.services.experiment_service import ExperimentService
    exp_svc = ExperimentService(db_path=str(tmp_path / "exp.db"))

    mock_pipeline = MagicMock()
    mock_pipeline.retrieve = AsyncMock(return_value=[
        RetrievalResult(document_id="doc1", page_number=1, score=0.9, image_path="/a.png"),
    ])
    mock_manager = MagicMock()
    mock_manager.pipeline = mock_pipeline
    mock_manager.get_current_config.return_value = {"retriever": "multi_vector"}

    app = create_app(
        worker_client=MagicMock(),
        pipeline_manager=mock_manager,
        document_service=MagicMock(),
        experiment_service=exp_svc,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/experiments/evaluate", json={
            "queries": [{"query": "q1", "relevant": ["doc1:1"]}],
            "top_k": 5,
            "note": "test run",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "experiment_id" in data
    assert data["total_queries"] == 1

    # Verify it was persisted
    rows = exp_svc.list_experiments()
    assert len(rows) == 1
    assert rows[0]["note"] == "test run"


@pytest.mark.asyncio
async def test_get_experiment_history(tmp_path):
    from backend.services.experiment_service import ExperimentService
    exp_svc = ExperimentService(db_path=str(tmp_path / "exp.db"))
    exp_svc.record(pipeline_config={"r": "a"}, metrics={"mrr": 0.5}, total_queries=5)

    app = create_app(
        worker_client=MagicMock(),
        pipeline_manager=MagicMock(),
        document_service=MagicMock(),
        experiment_service=exp_svc,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/experiments/history")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["metrics"]["mrr"] == 0.5
