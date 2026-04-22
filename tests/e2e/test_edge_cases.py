"""E2E tests: error paths, boundary values, 4xx/5xx contracts."""
import pytest

pytestmark = pytest.mark.e2e


def test_upload_empty_file_rejected(client):
    r = client.post(
        "/api/documents/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert r.status_code in (400, 422), f"Expected 4xx, got {r.status_code}: {r.text}"


def test_upload_text_file_rejected(client):
    r = client.post(
        "/api/documents/upload",
        files={"file": ("not_a_pdf.txt", b"hello world", "text/plain")},
    )
    assert r.status_code in (400, 422), f"Expected 4xx, got {r.status_code}: {r.text}"


def test_query_empty_string_no_crash(client):
    r = client.post("/api/query", json={"query": "", "top_k": 5})
    assert r.status_code in (200, 400, 422), f"Unexpected status {r.status_code}: {r.text}"
    # Must NOT be 500
    assert r.status_code != 500


def test_retrieve_very_large_top_k(client):
    r = client.post("/api/retrieve", json={"query": "test", "top_k": 1000})
    assert r.status_code in (200, 400, 422)
    assert r.status_code != 500


def test_evaluate_empty_queries_graceful(client):
    r = client.post("/api/experiments/evaluate", json={"queries": [], "top_k": 5})
    assert r.status_code == 200
    assert r.json()["total_queries"] == 0
    assert r.json()["mrr"] == 0.0


def test_get_nonexistent_experiment(client):
    r = client.get("/api/experiments/999999")
    assert r.status_code == 404


def test_delete_nonexistent_experiment(client):
    r = client.delete("/api/experiments/999999")
    assert r.status_code == 404


def test_pipeline_switch_to_nonexistent_retriever(client):
    r = client.put(
        "/api/pipelines/active",
        json={
            "processor": "colpali",
            "document_encoder": "colpali",
            "query_encoder": "colpali",
            "retriever": "nonexistent_retriever_xyz",
            "reranker": None,
            "generator": "claude",
        },
    )
    assert r.status_code in (400, 422, 500)
    # Should NOT silently succeed
    assert r.status_code != 200


def test_chat_empty_messages_list(client):
    r = client.post("/api/chat", json={"messages": [], "top_k": 3})
    assert r.status_code in (400, 422)


def test_health_endpoint_structure(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "worker" in data
    assert "qdrant" in data
    assert data["worker"]["status"] in ("ok", "error", "unknown")
    assert data["qdrant"]["status"] in ("ok", "error", "unknown")
