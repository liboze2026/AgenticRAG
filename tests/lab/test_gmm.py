"""Unit tests for Phase 3 — GMM dynamic top-k."""
import pytest

from backend.lab.gmm import gmm_dynamic_topk, is_sklearn_available
from backend.models.schemas import RetrievalResult


def make_results(scores):
    return [
        RetrievalResult(document_id=f"d{i}", page_number=i + 1, score=float(s),
                        image_path=f"page_{i + 1}.png")
        for i, s in enumerate(scores)
    ]


def test_empty_candidates():
    resp = gmm_dynamic_topk("q", [], fixed_top_k=5)
    assert resp.dynamic_top_k == 0
    assert resp.results == []
    assert "无候选" in resp.note


def test_too_few_candidates_falls_back():
    resp = gmm_dynamic_topk("q", make_results([0.9, 0.5]), fixed_top_k=5)
    # Falls back to fixed top-k (capped at len)
    assert resp.dynamic_top_k <= 2
    assert "退化" in resp.note or "太少" in resp.note


def test_uniform_scores_falls_back():
    resp = gmm_dynamic_topk("q", make_results([0.5] * 10), fixed_top_k=5)
    assert "退化" in resp.note or "无信息" in resp.note


@pytest.mark.skipif(not is_sklearn_available(), reason="sklearn not installed")
def test_bimodal_picks_high_cluster():
    # 5 high-scoring + 15 low-scoring -> GMM should pick ~5 as dynamic top-k
    high = [0.9, 0.88, 0.87, 0.85, 0.84]
    low = [0.15 + i * 0.005 for i in range(15)]
    resp = gmm_dynamic_topk("q", make_results(high + low), fixed_top_k=10)
    assert resp.dynamic_top_k >= 3
    assert resp.dynamic_top_k <= 8
    assert resp.cutoff_score > 0.4   # cutoff lies between the two peaks
    assert len(resp.components) == 2
    high_comp = max(resp.components, key=lambda c: c.mean)
    low_comp  = min(resp.components, key=lambda c: c.mean)
    assert high_comp.mean > low_comp.mean


@pytest.mark.skipif(not is_sklearn_available(), reason="sklearn not installed")
def test_histogram_built():
    scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    resp = gmm_dynamic_topk("q", make_results(scores), fixed_top_k=4)
    total = sum(b.count for b in resp.histogram)
    assert total == len(scores)


@pytest.mark.skipif(not is_sklearn_available(), reason="sklearn not installed")
def test_dynamic_top_k_bounded_by_max_ratio():
    # With 20 candidates and max_k_ratio=0.8, dynamic_top_k ≤ 16
    n = 20
    scores = [0.9 - i * 0.001 for i in range(n)]
    resp = gmm_dynamic_topk("q", make_results(scores), fixed_top_k=5,
                             max_k_ratio=0.8)
    assert resp.dynamic_top_k <= int(n * 0.8)


def test_results_truncated_to_dynamic():
    scores = [0.9, 0.85, 0.8, 0.5, 0.4, 0.3, 0.2, 0.1]
    resp = gmm_dynamic_topk("q", make_results(scores), fixed_top_k=4)
    # Whatever path was taken, results length must equal dynamic_top_k
    assert len(resp.results) == resp.dynamic_top_k
