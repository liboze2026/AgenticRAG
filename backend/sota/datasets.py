"""VisDoMBench dataset loader + integrity checker.

Phase 0 only consumes locally-cached metadata (queries.jsonl per subset).
Page images live on the remote worker filesystem; methods request encodings
through the worker rather than touching images directly.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

PageKey = Tuple[str, int]

# Subset names as stored on the active server's VisDoM-main directory.
# The published VisDoMBench paper covers FetaTab, MMLongBench, PaperTab,
# SlideVQA. This server's copy substitutes scigraphvqa and spiqa for
# MMLongBench (which isn't present on disk). The system reports actual
# subsets discovered on disk; methods are subset-agnostic.
SUBSETS: Tuple[str, ...] = ("feta_tab", "paper_tab", "scigraphvqa", "slidevqa", "spiqa")
# Reference: subsets reported in the VisDoMBench paper (Suri et al. 2025).
# Used only as a baseline-comparison label in reports.
PAPER_SUBSETS: Tuple[str, ...] = ("FetaTab", "MMLongBench", "PaperTab", "SlideVQA")


@dataclass
class SotaQuery:
    """One VisDoMBench retrieval query.

    Methods receive these via load_local_queries(). Methods MUST NOT see
    gold_pages — that lives in the evaluator scope only.
    """
    query_id: str
    subset: str
    query: str
    gold_pages: List[PageKey] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


def count_local_queries(root: str, subset: str) -> int:
    p = os.path.join(root, subset, "queries.jsonl")
    if not os.path.exists(p):
        return 0
    n = 0
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def _query_split(query_id: str) -> str:
    """Deterministic train/test split.

    Hash query_id; bottom half (h<32768) → train, top half → test.
    Stable across runs; an individual query is always in the same split.
    """
    import hashlib
    h = int(hashlib.sha1(query_id.encode("utf-8")).hexdigest()[:4], 16)
    return "train" if h < 32768 else "test"


def load_local_queries(
    root: str, subset: str, limit: Optional[int] = None,
    split: Optional[str] = None,
) -> Iterator[SotaQuery]:
    """Iterate SotaQuery records.

    split=None: return all queries.
    split="train" / "test": filter by deterministic hash of query_id.
    """
    p = os.path.join(root, subset, "queries.jsonl")
    if not os.path.exists(p):
        return
    emitted = 0
    with open(p, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            qid = str(row.get("query_id") or f"{subset}_{i}")
            if split not in (None, "all") and _query_split(qid) != split:
                continue
            if limit is not None and emitted >= limit:
                break
            emitted += 1
            doc_ids = row.get("gold_doc_ids") or []
            pages = row.get("gold_page_numbers") or []
            gold: List[PageKey] = []
            for d, pg in zip(doc_ids, pages):
                try:
                    gold.append((str(d), int(pg)))
                except (TypeError, ValueError):
                    continue
            # If the row already has a nested "metadata" dict (from our
            # CSV→JSONL converter), use it directly. Otherwise fall back to
            # collecting unknown top-level keys.
            nested_meta = row.get("metadata")
            if isinstance(nested_meta, dict):
                meta = nested_meta
            else:
                meta = {
                    k: v for k, v in row.items()
                    if k not in {"query_id", "query", "gold_doc_ids", "gold_page_numbers"}
                }
            yield SotaQuery(
                query_id=qid,
                subset=subset,
                query=str(row.get("query", "")),
                gold_pages=gold,
                metadata=meta,
            )


@dataclass
class DatasetIntegrity:
    subsets: Dict[str, Dict] = field(default_factory=dict)

    @classmethod
    def scan(cls, root: str) -> "DatasetIntegrity":
        out: Dict[str, Dict] = {}
        for s in SUBSETS:
            p = os.path.join(root, s, "queries.jsonl")
            if not os.path.exists(p):
                out[s] = {"status": "missing", "path": p, "query_count": 0}
                continue
            n = count_local_queries(root, s)
            out[s] = {
                "status": "ok" if n > 0 else "empty",
                "path": p,
                "query_count": n,
            }
        return cls(subsets=out)

    def to_dict(self) -> Dict:
        return {"subsets": self.subsets}
