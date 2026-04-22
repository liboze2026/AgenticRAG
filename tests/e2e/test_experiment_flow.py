"""E2E tests: experiment evaluation, metrics correctness, history, hard negatives."""
import pytest

pytestmark = pytest.mark.e2e


def _eval_payload(doc_id: str, page: int = 1):
    return {
        "queries": [
            {"query": "What is in this document?", "relevant": [f"{doc_id}:{page}"]},
        ],
        "top_k": 5,
        "note": "e2e test experiment",
    }


def test_evaluate_returns_metrics(client, indexed_doc):
    r = client.post("/api/experiments/evaluate", json=_eval_payload(indexed_doc))
    assert r.status_code == 200
    data = r.json()
    assert "experiment_id" in data
    assert "mrr" in data
    assert "recall_at_k" in data
    assert "total_queries" in data
    assert data["total_queries"] == 1
    # White-box: mrr must be in [0, 1]
    assert 0.0 <= data["mrr"] <= 1.0


def test_metrics_monotone_recall(client, indexed_doc):
    r = client.post("/api/experiments/evaluate", json=_eval_payload(indexed_doc))
    assert r.status_code == 200
    recall = r.json()["recall_at_k"]
    # JSON serialises integer dict-keys as strings: "1", "5", "10"
    r1 = recall.get("1", recall.get(1, 0))
    r5 = recall.get("5", recall.get(5, 0))
    r10 = recall.get("10", recall.get(10, 0))
    assert r1 <= r5 <= r10, f"Recall not monotone: {r1} > {r5} or {r5} > {r10}"


def test_experiment_appears_in_history(client, indexed_doc):
    r = client.post("/api/experiments/evaluate", json=_eval_payload(indexed_doc))
    assert r.status_code == 200
    exp_id = r.json()["experiment_id"]

    r_hist = client.get("/api/experiments/history")
    assert r_hist.status_code == 200
    # History items use "id" (not "experiment_id") per experiment_service._row_to_dict
    exp_ids = [e["id"] for e in r_hist.json()]
    assert exp_id in exp_ids


def test_get_experiment_detail(client, indexed_doc):
    r = client.post("/api/experiments/evaluate", json=_eval_payload(indexed_doc))
    exp_id = r.json()["experiment_id"]

    r_detail = client.get(f"/api/experiments/{exp_id}")
    assert r_detail.status_code == 200
    data = r_detail.json()
    # Both pipeline_config and metrics are always present per _row_to_dict
    assert "pipeline_config" in data
    assert "metrics" in data


def test_delete_experiment(client, indexed_doc):
    r = client.post("/api/experiments/evaluate", json=_eval_payload(indexed_doc))
    exp_id = r.json()["experiment_id"]

    del_r = client.delete(f"/api/experiments/{exp_id}")
    assert del_r.status_code == 200

    get_r = client.get(f"/api/experiments/{exp_id}")
    assert get_r.status_code == 404


def test_hard_negatives_augment(client, indexed_doc):
    eval_data = [
        {"query": "Test query", "relevant": [f"{indexed_doc}:1"]},
    ]
    r = client.post(
        "/api/experiments/hard_negatives",
        json={"eval_data": eval_data, "window": 1},
    )
    assert r.status_code == 200
    result = r.json()
    assert "eval_data" in result
    assert len(result["eval_data"]) == 1


def test_evaluate_zero_queries_graceful(client):
    r = client.post(
        "/api/experiments/evaluate",
        json={"queries": [], "top_k": 5},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total_queries"] == 0
    assert data["mrr"] == 0.0
    # recall_at_k is an empty dict when there are no queries
    assert data["recall_at_k"] == {}
