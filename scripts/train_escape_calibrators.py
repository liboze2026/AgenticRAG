"""Fit isotonic regression calibrators per (subset, channel) on train split.

Outputs data/sota_runs/escape/<subset>.json with:
  {channel: {thresholds: [...], probs: [...]}}

Used by closed_set_escape for test-time piecewise-linear lookup.
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError: pass
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import numpy as np

from backend.sota.datasets import load_local_queries, SUBSETS
from backend.sota.methods import MethodContext
from backend.sota.methods.closed_set_bm25_page import _run as _bm_page
from backend.sota.methods.closed_set_bm25_text import _run as _bm_text
from backend.sota.methods.closed_set_dense import _run as _dense
from backend.sota.methods.closed_set_titlematch import _run as _title
from backend.sota.service import build_sota_bundle

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("escape_train")

OUT_ROOT = os.path.join("data", "sota_runs", "escape")
os.makedirs(OUT_ROOT, exist_ok=True)


def _rank_dict(ranked: List[Tuple[str, int, float]]) -> Dict[Tuple[str, int], float]:
    return {(d, p): 1.0 / (i + 1) for i, (d, p, _s) in enumerate(ranked)}


def _isotonic_pava(scores: List[float], labels: List[int]) -> Tuple[List[float], List[float]]:
    """Pool Adjacent Violators isotonic regression. Returns (sorted_scores, sorted_probs).

    Standard implementation via PAVA on score-sorted (label) values; bins
    of consecutive equal predictions are then collapsed.
    """
    if not scores:
        return [], []
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    s = [float(scores[i]) for i in order]
    y = [float(labels[i]) for i in order]

    # PAVA
    n = len(y)
    out = list(y)
    weight = [1.0] * n
    i = 0
    while i < n - 1:
        if out[i] > out[i + 1]:
            # Merge
            tot_w = weight[i] + weight[i + 1]
            mean = (out[i] * weight[i] + out[i + 1] * weight[i + 1]) / tot_w
            out[i] = mean
            weight[i] = tot_w
            del out[i + 1]
            del weight[i + 1]
            del s[i + 1]   # collapse score too (keep first)
            n -= 1
            if i > 0:
                i -= 1
        else:
            i += 1
    # Clip to [0, 1]
    out = [min(1.0, max(0.0, v)) for v in out]
    return s, out


async def _collect_for_subset(subset: str, ctx: MethodContext, n_train: int):
    qs = list(load_local_queries(
        "data/sota_runs/datasets", subset, limit=n_train, split="train",
    ))
    logger.info("[%s] %d train queries", subset, len(qs))
    rows = {ch: [] for ch in ("bm25_text", "bm25_page", "dense", "title")}
    for q in qs:
        cand = (q.metadata or {}).get("candidate_docs", []) or []
        if not cand: continue
        gold_docs = {d for (d, _p) in q.gold_pages}
        a, b, c, d = await asyncio.gather(
            _bm_text(q, 30, ctx),
            _bm_page(q, 30, ctx),
            _dense(q, 30, ctx),
            _title(q, 30, ctx),
        )
        rd = {"bm25_text": _rank_dict(a), "bm25_page": _rank_dict(b),
              "dense": _rank_dict(c), "title": _rank_dict(d)}
        keys = set(rd["bm25_text"]) | set(rd["bm25_page"]) | set(rd["dense"]) | set(rd["title"])
        for k in keys:
            label = 1 if k[0] in gold_docs else 0
            for ch in rows:
                rows[ch].append((rd[ch].get(k, 0.0), label))
    return rows


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subsets", nargs="+",
                    default=["feta_tab", "paper_tab", "scigraphvqa", "spiqa"])
    ap.add_argument("--n_train", type=int, default=120)
    args = ap.parse_args()

    bundle = build_sota_bundle(
        sota_data_root="data/sota_runs/datasets",
        runs_root="data/sota_runs",
        pipeline=None, lab_bundle=None,
        qdrant_client=None, worker_client=None,
    )
    ctx = MethodContext(
        pipeline=None, lab_bundle=None,
        qdrant_client=None, worker_client=None,
        extras={"corpus": bundle.corpus},
    )
    for subset in args.subsets:
        rows = await _collect_for_subset(subset, ctx, args.n_train)
        cal = {}
        for ch, sl in rows.items():
            if not sl:
                continue
            scores = [s for (s, _l) in sl]
            labels = [l for (_s, l) in sl]
            t, p = _isotonic_pava(scores, labels)
            cal[ch] = {"thresholds": t, "probs": p}
        out_path = os.path.join(OUT_ROOT, f"{subset}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(cal, f, indent=2)
        logger.info("[%s] saved %d channel calibrators → %s",
                    subset, len(cal), out_path)


if __name__ == "__main__":
    asyncio.run(main())
