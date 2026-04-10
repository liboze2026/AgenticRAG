import pytest
from backend.services.evaluation import compute_recall_at_k, compute_mrr


def test_recall_at_1_hit():
    assert compute_recall_at_k(["doc1:1", "doc2:3", "doc1:2"], {"doc1:1"}, k=1) == 1.0

def test_recall_at_1_miss():
    assert compute_recall_at_k(["doc2:3", "doc1:1", "doc1:2"], {"doc1:1"}, k=1) == 0.0

def test_recall_at_5():
    assert compute_recall_at_k(["a", "b", "c", "d", "e"], {"c", "e"}, k=5) == 1.0

def test_recall_at_3_partial():
    assert compute_recall_at_k(["a", "b", "c", "d", "e"], {"c", "e"}, k=3) == 0.5

def test_mrr_first():
    assert compute_mrr(["a", "b", "c"], {"a"}) == 1.0

def test_mrr_second():
    assert compute_mrr(["a", "b", "c"], {"b"}) == 0.5

def test_mrr_none():
    assert compute_mrr(["a", "b", "c"], {"d"}) == 0.0
