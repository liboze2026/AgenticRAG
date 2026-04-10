import pytest
from backend.services.cache import DiskCache


def test_disabled_cache_returns_none(tmp_path):
    cache = DiskCache(path=str(tmp_path / "c"), enabled=False)
    cache.set("k", "v")
    assert cache.get("k") is None


def test_enabled_cache_round_trips(tmp_path):
    cache = DiskCache(path=str(tmp_path / "c"), enabled=True)
    cache.set("k", {"a": 1})
    assert cache.get("k") == {"a": 1}


def test_missing_key_returns_none(tmp_path):
    cache = DiskCache(path=str(tmp_path / "c"), enabled=True)
    assert cache.get("missing") is None


def test_clear_removes_all(tmp_path):
    cache = DiskCache(path=str(tmp_path / "c"), enabled=True)
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.clear() == 2
    assert cache.get("a") is None


def test_stats(tmp_path):
    cache = DiskCache(path=str(tmp_path / "c"), enabled=True)
    cache.set("a", "x")
    s = cache.stats()
    assert s["enabled"] is True
    assert s["entries"] == 1
    assert s["size_bytes"] > 0
