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
SUBSETS: Tuple[str, ...] = ("fetatab", "mmlongbench", "papertab", "slidevqa")


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


def load_local_queries(root: str, subset: str, limit: Optional[int] = None) -> Iterator[SotaQuery]:
    p = os.path.join(root, subset, "queries.jsonl")
    if not os.path.exists(p):
        return
    with open(p, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                break
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            doc_ids = row.get("gold_doc_ids") or []
            pages = row.get("gold_page_numbers") or []
            gold: List[PageKey] = []
            for d, pg in zip(doc_ids, pages):
                try:
                    gold.append((str(d), int(pg)))
                except (TypeError, ValueError):
                    continue
            yield SotaQuery(
                query_id=str(row.get("query_id") or f"{subset}_{i}"),
                subset=subset,
                query=str(row.get("query", "")),
                gold_pages=gold,
                metadata={k: v for k, v in row.items() if k not in {
                    "query_id", "query", "gold_doc_ids", "gold_page_numbers",
                }},
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
