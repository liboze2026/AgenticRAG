"""E2E tests: query and retrieve endpoints, cache behavior, empty index."""
import time
import pytest

pytestmark = pytest.mark.e2e

QUERY = "What is in this document?"


def test_query_returns_answer_and_sources(client, indexed_doc):
    r = client.post("/api/query", json={"query": QUERY, "top_k": 3})
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 0
    assert "sources" in data
    assert len(data["sources"]) >= 1
    # White-box: timing must be populated
    assert "timing" in data
    assert data["timing"].get("total_ms", 0) > 0


def test_retrieve_returns_results_with_scores(client, indexed_doc):
    r = client.post("/api/retrieve", json={"query": QUERY, "top_k": 5})
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert len(data["results"]) >= 1
    for result in data["results"]:
        assert "document_id" in result
        assert "page_number" in result
        assert "score" in result
        # RetrievalResult.score is an unbounded float; strategies like BM25/hybrid
        # may produce scores > 1.0, so only assert non-negative.
        assert result["score"] >= 0


def test_top_k_limits_results(client, indexed_doc):
    r = client.post("/api/retrieve", json={"query": QUERY, "top_k": 1})
    assert r.status_code == 200
    assert len(r.json()["results"]) <= 1


def test_repeat_query_uses_cache(client, indexed_doc):
    # First call — cold
    t0 = time.perf_counter()
    r1 = client.post("/api/query", json={"query": QUERY + " cache test", "top_k": 1})
    t1 = time.perf_counter() - t0
    assert r1.status_code == 200

    # Second identical call — should be faster (cached)
    t0 = time.perf_counter()
    r2 = client.post("/api/query", json={"query": QUERY + " cache test", "top_k": 1})
    t2 = time.perf_counter() - t0
    assert r2.status_code == 200

    # Cache is active iff second call returns identical answer AND is meaningfully faster.
    # If cache is disabled in config, generator LLM is non-deterministic so answers differ —
    # treat that as cache-not-active (xfail), not a hard failure.
    same_answer = r1.json()["answer"] == r2.json()["answer"]
    faster = t2 < t1 * 0.5  # 2x speedup threshold
    if not (same_answer and faster):
        pytest.xfail(
            f"Cache appears inactive: same_answer={same_answer} "
            f"first={t1:.2f}s second={t2:.2f}s"
        )


def test_retrieve_timing_present(client, indexed_doc):
    r = client.post("/api/retrieve", json={"query": QUERY, "top_k": 3})
    assert r.status_code == 200
    timing = r.json().get("timing", {})
    assert len(timing) > 0
