"""Closed-set learned-fusion ranking.

Trained MLP head fuses multiple per-channel scores into a unified relevance
score. Trained on a held-out subset of train queries (NOT test queries —
academic-integrity guard).

Training script: scripts/train_fusion_head.py.
Model file: data/sota_runs/fusion_head/<subset>.pt + meta.json (channels).

If model file missing → falls back to closed_set_hybrid.

Channels (per page candidate):
  0: bm25_text (rank-normalized)
  1: bm25_page (rank-normalized)
  2: dense (cosine)
  3: titlematch (rank-normalized)

Score is computed concurrently per query, then the trained head produces a
final score per (page, channels). Sort, top-k.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from typing import Dict, List, Optional, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.closed_set_bm25_page import _run as _bm_page
from backend.sota.methods.closed_set_bm25_text import _run as _bm_text
from backend.sota.methods.closed_set_dense import _run as _dense
from backend.sota.methods.closed_set_titlematch import _run as _title

logger = logging.getLogger(__name__)


_HEAD_LOCK = threading.Lock()
_HEADS: Dict[str, object] = {}
_HEAD_ROOT = os.path.join("data", "sota_runs", "fusion_head")


def _load_head(subset: str):
    if subset in _HEADS:
        return _HEADS[subset]
    with _HEAD_LOCK:
        if subset in _HEADS:
            return _HEADS[subset]
        path = os.path.join(_HEAD_ROOT, f"{subset}.pt")
        if not os.path.exists(path):
            _HEADS[subset] = None
            return None
        try:
            import torch
            head = torch.jit.load(path, map_location="cpu").eval()
            _HEADS[subset] = head
            logger.info("[fusion] %s loaded from %s", subset, path)
            return head
        except Exception as e:
            logger.warning("[fusion] %s load failed: %s", subset, e)
            _HEADS[subset] = None
            return None


def _rank_normalize(ranked: List[Tuple[str, int, float]]) -> Dict[Tuple[str, int], float]:
    """Convert ranked (doc, page, score) to {(doc, page): 1/(rank+1)}."""
    out: Dict[Tuple[str, int], float] = {}
    for i, (d, p, _s) in enumerate(ranked):
        out[(d, p)] = 1.0 / (i + 1)
    return out


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    head = _load_head(query.subset)
    if head is None:
        from backend.sota.methods.closed_set_hybrid import _run as _hy
        return await _hy(query, top_k, ctx)
    candidates = (query.metadata or {}).get("candidate_docs", []) or []
    if not candidates:
        return []
    k_in = top_k * 4
    a, b, c, d = await asyncio.gather(
        _bm_text(query, k_in, ctx),
        _bm_page(query, k_in, ctx),
        _dense(query, k_in, ctx),
        _title(query, k_in, ctx),
    )
    a_n = _rank_normalize(a)
    b_n = _rank_normalize(b)
    c_n = _rank_normalize(c)
    d_n = _rank_normalize(d)

    keys = set(a_n) | set(b_n) | set(c_n) | set(d_n)
    if not keys:
        return []
    try:
        import numpy as np
        import torch
    except ImportError:
        from backend.sota.methods.closed_set_hybrid import _run as _hy
        return await _hy(query, top_k, ctx)

    keys = list(keys)
    feats = np.array([
        [a_n.get(k, 0.0), b_n.get(k, 0.0), c_n.get(k, 0.0), d_n.get(k, 0.0)]
        for k in keys
    ], dtype="float32")
    with torch.no_grad():
        scores = head(torch.from_numpy(feats)).cpu().numpy().reshape(-1)
    order = scores.argsort()[::-1][:top_k]
    return [(keys[i][0], keys[i][1], float(scores[i])) for i in order]


register(MethodMeta(
    name="closed_set_learned_fusion",
    version="1.0",
    description="MLP head fusing bm25_text/bm25_page/dense/titlematch (trained on train split).",
    needs=["fusion_head_pt"],
    uses_test_labels=False,
    run=_run,
))
