"""Unit tests for Phase 9 benchmark eval helper."""
from backend.lab.benchmark import _eval_one
from backend.lab.schemas import GraphSeed
from backend.models.schemas import RetrievalResult


def _r(doc, page, score=0.5):
    return RetrievalResult(
        document_id=doc, page_number=page, score=score,
        image_path=f"/img/{doc}/{page}.png",
    )


def _gs(doc, page):
    return GraphSeed(document_id=doc, page_number=page)


def test_eval_one_perfect_hit_at_one():
    retrieved = [_r("d1", 5), _r("d1", 6), _r("d1", 7)]
    relevant = [_gs("d1", 5)]
    rr, r5, r10, h1 = _eval_one(retrieved, relevant)
    assert rr == 1.0
    assert r5 == 1.0
    assert r10 == 1.0
    assert h1 == 1.0


def test_eval_one_first_hit_at_three():
    retrieved = [_r("d1", 1), _r("d1", 2), _r("d1", 5), _r("d1", 7)]
    relevant = [_gs("d1", 5)]
    rr, r5, r10, h1 = _eval_one(retrieved, relevant)
    assert rr == 1.0 / 3
    assert r5 == 1.0
    assert h1 == 0.0


def test_eval_one_no_hit():
    retrieved = [_r("d1", 1), _r("d1", 2)]
    relevant = [_gs("d1", 99)]
    rr, r5, r10, h1 = _eval_one(retrieved, relevant)
    assert rr == 0.0
    assert r5 == 0.0
    assert h1 == 0.0


def test_eval_one_partial_recall():
    retrieved = [_r("d1", 1), _r("d1", 2), _r("d1", 3), _r("d1", 4), _r("d1", 5)]
    relevant = [_gs("d1", 1), _gs("d1", 5), _gs("d1", 99)]   # only 2 of 3 in top-5
    rr, r5, r10, h1 = _eval_one(retrieved, relevant)
    assert rr == 1.0
    assert r5 == pytest.approx(2.0 / 3)
    assert h1 == 1.0


def test_eval_one_empty_inputs():
    rr, r5, r10, h1 = _eval_one([], [])
    assert (rr, r5, r10, h1) == (0.0, 0.0, 0.0, 0.0)


# pytest used as approx — import lazily to avoid hard dep at module level
import pytest  # noqa: E402
