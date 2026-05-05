"""VisDoMBench per-doc text corpus.

Loads `data/sota_runs/corpus/<subset>.jsonl` (page-level text records) into
in-memory dicts:
    text_by_subset_doc[(subset, doc_id)] = " ".join(page texts)
    pages_by_subset_doc[(subset, doc_id)] = [(page_number, text), ...]

Lazy-loaded on first access; thread-safe (single-process FastAPI).
Memory budget: ~100 MB total expected for all 5 subsets.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class VisDomCorpus:
    def __init__(self, root: str, ocr_root: Optional[str] = None):
        self.root = root
        # OCR-extracted text (e.g. for slidevqa whose PDFs are image-only)
        # is loaded from this directory and unioned into the same maps.
        self.ocr_root = ocr_root or os.path.join(os.path.dirname(root), "corpus_ocr")
        self._text_lock = threading.Lock()
        self._loaded: Dict[str, bool] = {}
        # (subset, doc_id) → concatenated page text
        self._text_by_doc: Dict[Tuple[str, str], str] = {}
        # (subset, doc_id) → [(page_number, text), ...]
        self._pages_by_doc: Dict[Tuple[str, str], List[Tuple[int, str]]] = {}

    def _path(self, subset: str) -> str:
        return os.path.join(self.root, f"{subset}.jsonl")

    def _ocr_path(self, subset: str) -> str:
        return os.path.join(self.ocr_root, f"{subset}.jsonl")

    def is_available(self, subset: str) -> bool:
        p = self._path(subset)
        op = self._ocr_path(subset)
        return (os.path.exists(p) and os.path.getsize(p) > 0) or \
               (os.path.exists(op) and os.path.getsize(op) > 0)

    def _load_one_file(self, subset: str, path: str) -> int:
        """Append one jsonl into the in-memory maps. Returns # new docs."""
        if not os.path.exists(path):
            return 0
        seen_before = {k for k in self._text_by_doc.keys() if k[0] == subset}
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                doc = str(row.get("doc_id", ""))
                pg = int(row.get("page_number", 0) or 0)
                text = str(row.get("text", ""))
                if not doc:
                    continue
                key = (subset, doc)
                self._pages_by_doc.setdefault(key, []).append((pg, text))
                if key in self._text_by_doc:
                    self._text_by_doc[key] += "\n" + text
                else:
                    self._text_by_doc[key] = text
        seen_after = {k for k in self._text_by_doc.keys() if k[0] == subset}
        return len(seen_after - seen_before)

    def load_subset(self, subset: str) -> int:
        with self._text_lock:
            if self._loaded.get(subset):
                return sum(
                    1 for k in self._text_by_doc.keys() if k[0] == subset
                )
            n_text = self._load_one_file(subset, self._path(subset))
            n_ocr = self._load_one_file(subset, self._ocr_path(subset))
            self._loaded[subset] = True
            count = sum(1 for k in self._text_by_doc.keys() if k[0] == subset)
            logger.info(
                "[corpus] %s loaded: %d docs (text=%d, ocr=%d)",
                subset, count, n_text, n_ocr,
            )
            return count

    def doc_text(self, subset: str, doc_id: str) -> Optional[str]:
        if not self._loaded.get(subset):
            self.load_subset(subset)
        return self._text_by_doc.get((subset, doc_id))

    def doc_pages(self, subset: str, doc_id: str) -> Optional[List[Tuple[int, str]]]:
        if not self._loaded.get(subset):
            self.load_subset(subset)
        return self._pages_by_doc.get((subset, doc_id))

    def stats(self) -> Dict[str, Dict]:
        out: Dict[str, Dict] = {}
        for subset in ("feta_tab", "paper_tab", "scigraphvqa", "slidevqa", "spiqa"):
            n_docs = sum(1 for k in self._text_by_doc.keys() if k[0] == subset)
            available = self.is_available(subset)
            out[subset] = {
                "available": available,
                "loaded": bool(self._loaded.get(subset)),
                "docs_loaded": n_docs,
                "path": self._path(subset),
            }
        return out
