import pytest

from backend.sota.eval import (
    PerQueryResult, aggregate_metrics, bootstrap_ci, score_query,
)


def test_score_query_hit_at_1():
    r = score_query(
        gold_pages=[("doc_a", 3)],
        ranked_pages=[("doc_a", 3), ("doc_a", 5), ("doc_b", 1)],
    )
    assert r.hit_at_1 == 1.0
    assert r.hit_at_3 == 1.0
    assert r.rr == pytest.approx(1.0)


def test_score_query_hit_at_3_only():
    r = score_query(
        gold_pages=[("doc_a", 7)],
        ranked_pages=[("doc_a", 1), ("doc_a", 7), ("doc_b", 1)],
    )
    assert r.hit_at_1 == 0.0
    assert r.hit_at_3 == 1.0
    assert r.rr == pytest.approx(0.5)


def test_score_query_miss():
    r = score_query(
        gold_pages=[("doc_a", 7)],
        ranked_pages=[("doc_b", 1), ("doc_b", 2), ("doc_b", 3)],
    )
    assert r.hit_at_1 == 0.0
    assert r.hit_at_3 == 0.0
    assert r.rr == 0.0


def test_score_query_multi_gold_first_hit_counts():
    r = score_query(
        gold_pages=[("doc_a", 7), ("doc_a", 9)],
        ranked_pages=[("doc_a", 9), ("doc_b", 1)],
    )
    assert r.hit_at_1 == 1.0
    assert r.rr == pytest.approx(1.0)


def test_aggregate_metrics():
    results = [
        PerQueryResult(query_id="q1", hit_at_1=1, hit_at_3=1, rr=1.0, latency_ms=10),
        PerQueryResult(query_id="q2", hit_at_1=0, hit_at_3=1, rr=0.5, latency_ms=10),
        PerQueryResult(query_id="q3", hit_at_1=0, hit_at_3=0, rr=0.0, latency_ms=10),
        PerQueryResult(query_id="q4", hit_at_1=1, hit_at_3=1, rr=1.0, latency_ms=10),
    ]
    agg = aggregate_metrics(results)
    assert agg["recall@1"] == pytest.approx(0.5)
    assert agg["recall@3"] == pytest.approx(0.75)
    assert agg["mrr"] == pytest.approx(0.625)
    assert agg["n"] == 4


def test_bootstrap_ci_returns_low_lt_high():
    values = [1.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0]
    lo, hi = bootstrap_ci(values, n_resamples=200, alpha=0.05, seed=1)
    assert 0.0 <= lo <= hi <= 1.0
    assert hi - lo > 0


def test_bootstrap_ci_empty():
    lo, hi = bootstrap_ci([], n_resamples=100)
    assert lo == 0.0 and hi == 0.0
