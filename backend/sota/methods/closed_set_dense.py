"""Closed-set dense-text retrieval.

Loads pre-computed bge-base-en-v1.5 embeddings (one per page) from
data/sota_runs/dense/<subset>.npz + .keys.jsonl, plus an in-process
SentenceTransformer for query encoding (CPU is fine — query encoding is
a single forward pass, ~50 ms).

For each query: encode → cosine similarity vs all pages of candidate docs
→ rank → return top-k (doc, page).

Falls back gracefully if dense files aren't present or sentence-transformers
isn't installed locally.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Dict, List, Optional, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register

logger = logging.getLogger(__name__)


_QUERY_ENCODER = None
_QUERY_ENCODER_LOCK = threading.Lock()
_PER_SUBSET_INDEX: Dict[str, Optional[Tuple[object, List[Tuple[str, int]]]]] = {}
_DENSE_ROOT = os.path.join("data", "sota_runs", "dense")
_MODEL_NAME = "BAAI/bge-base-en-v1.5"


def _load_query_encoder():
    global _QUERY_ENCODER
    if _QUERY_ENCODER is not None:
        return _QUERY_ENCODER
    with _QUERY_ENCODER_LOCK:
        if _QUERY_ENCODER is not None:
            return _QUERY_ENCODER
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            logger.warning("sentence-transformers not installed locally; closed_set_dense unavailable")
            _QUERY_ENCODER = False
            return False
        try:
            _QUERY_ENCODER = SentenceTransformer(_MODEL_NAME)
            logger.info("[dense] query encoder loaded")
        except Exception as e:
            logger.warning("[dense] could not load %s: %s", _MODEL_NAME, e)
            _QUERY_ENCODER = False
        return _QUERY_ENCODER


def _load_subset_index(subset: str):
    if subset in _PER_SUBSET_INDEX:
        return _PER_SUBSET_INDEX[subset]
    npz_path = os.path.join(_DENSE_ROOT, f"{subset}.npz")
    keys_path = os.path.join(_DENSE_ROOT, f"{subset}.keys.jsonl")
    if not (os.path.exists(npz_path) and os.path.exists(keys_path)):
        _PER_SUBSET_INDEX[subset] = None
        return None
    try:
        import numpy as np
    except ImportError:
        _PER_SUBSET_INDEX[subset] = None
        return None
    try:
        embs = np.load(npz_path)["embs"]
        keys = []
        with open(keys_path, "r", encoding="utf-8") as f:
            for line in f:
                k = json.loads(line)
                keys.append((str(k["doc_id"]), int(k["page_number"])))
        _PER_SUBSET_INDEX[subset] = (embs, keys)
        logger.info("[dense] %s loaded: %d page vectors", subset, len(keys))
        return _PER_SUBSET_INDEX[subset]
    except Exception as e:
        logger.warning("[dense] %s load failed: %s", subset, e)
        _PER_SUBSET_INDEX[subset] = None
        return None


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    candidates = (query.metadata or {}).get("candidate_docs", []) or []
    if not candidates:
        return []
    encoder = _load_query_encoder()
    if not encoder:
        from backend.sota.methods.closed_set_bm25_page import _run as _bm
        return await _bm(query, top_k, ctx)
    idx = _load_subset_index(query.subset)
    if idx is None:
        from backend.sota.methods.closed_set_bm25_page import _run as _bm
        return await _bm(query, top_k, ctx)

    embs, keys = idx
    try:
        import numpy as np
    except ImportError:
        from backend.sota.methods.closed_set_bm25_page import _run as _bm
        return await _bm(query, top_k, ctx)

    cand_set = set(candidates)
    mask = np.array([k[0] in cand_set for k in keys])
    if not mask.any():
        return []
    cand_embs = embs[mask]
    cand_keys = [k for k, m in zip(keys, mask) if m]

    # bge models prepend "query: " for retrieval
    q_text = "query: " + query.query
    q_vec = encoder.encode([q_text], normalize_embeddings=True, show_progress_bar=False)[0]
    sims = cand_embs @ q_vec
    order = sims.argsort()[::-1][:top_k]
    return [(cand_keys[i][0], cand_keys[i][1], float(sims[i])) for i in order]


register(MethodMeta(
    name="closed_set_dense",
    version="1.0",
    description="Page-level dense retrieval (bge-base-en-v1.5) within candidate set.",
    needs=["dense_index"],
    uses_test_labels=False,
    run=_run,
))
