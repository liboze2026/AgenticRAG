import pytest

from backend.sota.methods import METHOD_REGISTRY, MethodMeta, get_method
from backend.sota.methods.baseline_rrf import _rrf_fuse


def test_registry_has_three_baselines():
    assert "baseline_colpali" in METHOD_REGISTRY
    assert "baseline_bm25" in METHOD_REGISTRY
    assert "baseline_rrf" in METHOD_REGISTRY


def test_registry_meta_no_test_label_use():
    for meta in METHOD_REGISTRY.values():
        assert meta.uses_test_labels is False, (
            f"{meta.name}: methods must never see test labels"
        )


def test_get_method_returns_meta():
    m = get_method("baseline_colpali")
    assert isinstance(m, MethodMeta)
    assert m.name == "baseline_colpali"
    assert callable(m.run)


def test_rrf_fuse_basic():
    a = [("d1", 1), ("d1", 2), ("d2", 1)]
    b = [("d2", 1), ("d1", 1), ("d3", 1)]
    fused = _rrf_fuse([a, b], k=60, top_k=3)
    keys = [(d, p) for (d, p, _s) in fused]
    assert keys[0] in {("d1", 1), ("d2", 1)}
    assert ("d3", 1) not in keys[:2]


def test_rrf_fuse_handles_empty_channels():
    fused = _rrf_fuse([[], [("d1", 1)]], k=60, top_k=3)
    assert len(fused) == 1
    assert fused[0][0] == "d1"
