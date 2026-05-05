import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.sota.service import build_sota_bundle


@pytest.fixture
def client(tmp_path):
    sota_root = tmp_path / "sota"
    bundle = build_sota_bundle(
        sota_data_root=str(sota_root / "datasets"),
        runs_root=str(sota_root / "runs"),
        pipeline=None, lab_bundle=None,
        qdrant_client=None, worker_client=None,
    )
    app = create_app(sota_bundle=bundle)
    return TestClient(app)


def test_health_returns_envelope(client):
    r = client.get("/api/sota/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "methods" in body


def test_methods_lists_three_baselines(client):
    r = client.get("/api/sota/methods")
    body = r.json()
    names = {m["name"] for m in body["methods"]}
    assert {"baseline_colpali", "baseline_bm25", "baseline_rrf"} <= names


def test_datasets_returns_subset_status(client):
    r = client.get("/api/sota/datasets")
    body = r.json()
    assert body["ok"] is True
    assert set(body["subsets"].keys()) == {"feta_tab", "paper_tab", "scigraphvqa", "slidevqa", "spiqa"}


def test_unknown_run_returns_envelope_not_500(client):
    r = client.get("/api/sota/runs/not-a-real-id")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["error_kind"] == "run_not_found"


def test_create_run_with_bad_method_returns_envelope(client):
    r = client.post("/api/sota/runs", json={"methods": ["nonexistent"]})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["error_kind"] == "invalid_config"
