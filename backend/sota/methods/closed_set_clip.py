"""Closed-set CLIP image-text retrieval.

Pre-computed CLIP-ViT-B/32 image embeddings (one per page) live at
data/sota_runs/clip/<subset>.npz + .keys.jsonl. Only slidevqa is
expected to have CLIP embeddings — the other subsets are text-friendly.

Per query: encode query text with CLIP text tower → cosine vs candidate
page image embeddings → top-k.

Falls back to whatever bm25_text returns if CLIP files missing.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Dict, List, Optional, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register

logger = logging.getLogger(__name__)


_CLIP_MODEL = None
_CLIP_PROCESSOR = None
_CLIP_LOCK = threading.Lock()
_CLIP_INDEX: Dict[str, Optional[Tuple[object, List[Tuple[str, int]]]]] = {}
_CLIP_ROOT = os.path.join("data", "sota_runs", "clip")
_CLIP_NAME = "openai/clip-vit-base-patch32"


def _load_clip():
    global _CLIP_MODEL, _CLIP_PROCESSOR
    if _CLIP_MODEL is not None:
        return _CLIP_MODEL, _CLIP_PROCESSOR
    with _CLIP_LOCK:
        if _CLIP_MODEL is not None:
            return _CLIP_MODEL, _CLIP_PROCESSOR
        try:
            from transformers import CLIPModel, CLIPProcessor
            import torch  # noqa: F401
        except ImportError:
            logger.warning("transformers not available; closed_set_clip disabled")
            _CLIP_MODEL = False
            return False, None
        try:
            _CLIP_MODEL = CLIPModel.from_pretrained(_CLIP_NAME)
            _CLIP_MODEL.eval()
            _CLIP_PROCESSOR = CLIPProcessor.from_pretrained(_CLIP_NAME)
            logger.info("[clip] loaded %s (CPU only)", _CLIP_NAME)
        except Exception as e:
            logger.warning("[clip] load failed: %s", e)
            _CLIP_MODEL = False
        return _CLIP_MODEL, _CLIP_PROCESSOR


def _load_subset_index(subset: str):
    if subset in _CLIP_INDEX:
        return _CLIP_INDEX[subset]
    npz = os.path.join(_CLIP_ROOT, f"{subset}.npz")
    keys = os.path.join(_CLIP_ROOT, f"{subset}.keys.jsonl")
    if not (os.path.exists(npz) and os.path.exists(keys)):
        _CLIP_INDEX[subset] = None
        return None
    try:
        import numpy as np
    except ImportError:
        _CLIP_INDEX[subset] = None
        return None
    embs = np.load(npz)["embs"]
    ks: List[Tuple[str, int]] = []
    with open(keys, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            ks.append((str(row["doc_id"]), int(row["page_number"])))
    _CLIP_INDEX[subset] = (embs, ks)
    logger.info("[clip] %s: %d page vectors", subset, len(ks))
    return _CLIP_INDEX[subset]


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    candidates = (query.metadata or {}).get("candidate_docs", []) or []
    if not candidates:
        return []
    idx = _load_subset_index(query.subset)
    if idx is None:
        from backend.sota.methods.closed_set_bm25_text import _run as _t
        return await _t(query, top_k, ctx)
    model, processor = _load_clip()
    if not model:
        from backend.sota.methods.closed_set_bm25_text import _run as _t
        return await _t(query, top_k, ctx)

    try:
        import numpy as np
        import torch
    except ImportError:
        return []

    embs, keys = idx
    cand_set = set(candidates)
    mask = np.array([k[0] in cand_set for k in keys])
    if not mask.any():
        return []
    cand_embs = embs[mask]
    cand_keys = [k for k, m in zip(keys, mask) if m]

    inputs = processor(text=[query.query[:300]], return_tensors="pt", padding=True, truncation=True)
    with torch.no_grad():
        q_feat = model.get_text_features(**inputs)
        q_feat = torch.nn.functional.normalize(q_feat, dim=-1).cpu().numpy()[0]
    sims = cand_embs @ q_feat
    order = sims.argsort()[::-1][:top_k]
    return [(cand_keys[i][0], cand_keys[i][1], float(sims[i])) for i in order]


register(MethodMeta(
    name="closed_set_clip",
    version="1.0",
    description="CLIP-ViT-B/32 image-text retrieval (slidevqa); fallback bm25_text elsewhere.",
    needs=["clip_index"],
    uses_test_labels=False,
    run=_run,
))
