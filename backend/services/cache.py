"""Simple disk-backed cache with no external deps.

Usage:
    cache = DiskCache(path="data/cache/queries", enabled=True)
    val = cache.get(key)
    if val is None:
        val = expensive()
        cache.set(key, val)
"""
import hashlib
import logging
import os
import pickle
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DiskCache:
    """Key-value cache stored as pickle files on disk.

    Keys are hashed to filenames so any string is safe.
    Setting `enabled=False` makes get() always return None (effectively disabled).
    """

    def __init__(self, path: str, enabled: bool = False):
        self.path = path
        self.enabled = enabled
        if enabled:
            os.makedirs(path, exist_ok=True)

    def _key_to_path(self, key: str) -> str:
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return os.path.join(self.path, f"{h}.pkl")

    def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        fp = self._key_to_path(key)
        if not os.path.exists(fp):
            return None
        try:
            with open(fp, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            logger.warning("Cache read failed for key %s: %s", key, e)
            return None

    def set(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        fp = self._key_to_path(key)
        try:
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "wb") as f:
                pickle.dump(value, f)
        except Exception as e:
            logger.warning("Cache write failed for key %s: %s", key, e)

    def clear(self) -> int:
        """Delete all cached entries. Returns count deleted."""
        if not os.path.isdir(self.path):
            return 0
        count = 0
        for name in os.listdir(self.path):
            if name.endswith(".pkl"):
                try:
                    os.remove(os.path.join(self.path, name))
                    count += 1
                except OSError:
                    pass
        return count

    def stats(self) -> dict:
        if not os.path.isdir(self.path):
            return {"enabled": self.enabled, "entries": 0, "size_bytes": 0}
        entries = 0
        size = 0
        for name in os.listdir(self.path):
            if name.endswith(".pkl"):
                entries += 1
                try:
                    size += os.path.getsize(os.path.join(self.path, name))
                except OSError:
                    pass
        return {"enabled": self.enabled, "entries": entries, "size_bytes": size}
