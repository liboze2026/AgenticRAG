"""Closed-set ColPali multi-vector retrieval.

Loads pre-computed ColPali multi-vector embeddings (per-page, padded) from
data/sota_runs/colpali/<subset>.npz and ranks candidate pages via MaxSim
late-interaction.

Query encoding:
  * default: hits the existing worker via WorkerClient (already plumbed
    through the SSH tunnel by run.py). No new network code.
  * fallback: returns empty if no worker available (test isolation).

MaxSim:
  score(q, p) = sum_i max_j  q_i · p_j  (queries are short; pages have
  many patches; standard ColPali scoring formula).
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Dict, List, Optional, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register

logger = logging.getLogger(__name__)


_INDEX: Dict[str, Optional[Tuple[object, List[Tuple[str, int]], List[int]]]] = {}
_INDEX_LOCK = threading.Lock()
_ROOT = os.path.join("data", "sota_runs", "colpali")


def _load_subset_index(subset: str):
    if subset in _INDEX:
        return _INDEX[subset]
    with _INDEX_LOCK:
        if subset in _INDEX:
            return _INDEX[subset]
        npz = os.path.join(_ROOT, f"{subset}.npz")
        keys_p = os.path.join(_ROOT, f"{subset}.keys.jsonl")
        if not (os.path.exists(npz) and os.path.exists(keys_p)):
            _INDEX[subset] = None
            return None
        try:
            import numpy as np
        except ImportError:
            _INDEX[subset] = None
            return None
        embs = np.load(npz)["embs"]   # (M, max_p, dim) float16
        keys = []
        n_patches = []
        with open(keys_p, "r", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                keys.append((str(row["doc_id"]), int(row["page_number"])))
                n_patches.append(int(row.get("n_patches", embs.shape[1])))
        _INDEX[subset] = (embs, keys, n_patches)
        logger.info("[colpali] %s: %d pages, max_p=%d, dim=%d",
                    subset, len(keys), embs.shape[1], embs.shape[2])
        return _INDEX[subset]


async def _encode_query_via_worker(worker_client, query: str):
    """Returns (Q, dim) numpy float32 array via worker /encode/query."""
    if worker_client is None:
        return None
    try:
        out = await worker_client.encode_query(query)
    except Exception as e:
        logger.warning("[colpali] worker encode_query failed: %s", e)
        return None
    if out is None:
        return None
    try:
        import numpy as np
    except ImportError:
        return None
    arr = np.asarray(out, dtype="float32")
    if arr.ndim == 2 and arr.shape[0] > 0:
        return arr
    return None


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    candidates = (query.metadata or {}).get("candidate_docs", []) or []
    if not candidates:
        return []
    idx = _load_subset_index(query.subset)
    if idx is None:
        from backend.sota.methods.closed_set_clip import _run as _clip
        return await _clip(query, top_k, ctx)

    embs, keys, n_patches = idx
    try:
        import numpy as np
    except ImportError:
        return []

    cand_set = set(candidates)
    sel = [i for i, k in enumerate(keys) if k[0] in cand_set]
    if not sel:
        return []

    q_vec = await _encode_query_via_worker(ctx.worker_client, query.query)
    if q_vec is None:
        from backend.sota.methods.closed_set_clip import _run as _clip
        return await _clip(query, top_k, ctx)

    # Score each candidate page via MaxSim
    sel_embs = embs[sel].astype("float32")        # (M, P, D)
    sel_keys = [keys[i] for i in sel]
    sel_n = [n_patches[i] for i in sel]
    scores = np.zeros(len(sel), dtype="float32")
    Q = q_vec.shape[0]
    for j, (page_emb, n) in enumerate(zip(sel_embs, sel_n)):
        # page_emb shape (P, D); zero-padded after n
        active = page_emb[:n]                       # (n, D)
        sim = q_vec @ active.T                      # (Q, n)
        per_q_max = sim.max(axis=1)                 # (Q,)
        scores[j] = float(per_q_max.sum())          # MaxSim

    order = scores.argsort()[::-1][:top_k]
    return [(sel_keys[i][0], sel_keys[i][1], float(scores[i])) for i in order]


register(MethodMeta(
    name="closed_set_colpali",
    version="1.0",
    description="ColPali multi-vector + MaxSim late-interaction; query encoded via worker.",
    needs=["colpali_index", "worker_client"],
    uses_test_labels=False,
    run=_run,
))
