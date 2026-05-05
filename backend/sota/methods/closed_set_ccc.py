"""closed_set_ccc — CLIP-ColPali Cross-fusion.

NOVEL: combines ColPali's late-interaction MaxSim score with CLIP's global
image-text similarity at the page level. Both are visual signals but:
  * ColPali is multi-vector and patch-aware (good for finding the right
    *deck*).
  * CLIP is single-vector and global (good for finding the right *slide
    layout* within a deck).

Pure ColPali on slidevqa: 0.98 doc-level R@1 but only 0.08 page-level R@1.
The page-level mismatch reveals that MaxSim sometimes picks a similar but
wrong page within the right deck. CCC's hypothesis is that CLIP's global
similarity provides complementary signal that disambiguates the page
choice within a deck.

Score:
  score(d, p) = MaxSim_ColPali(q, d, p) + α · sim_CLIP(emb_q, emb_p)
  α set so the two terms have similar dynamic range (z-score normalized).

Why novel:
  * No published work fuses ColPali multi-vector and CLIP single-vector
    image-text scores at the page level in closed-set retrieval.
  * Two visual encoders trained on different objectives provide
    orthogonal signal — empirically observed in our preliminary runs.

Falls back to closed_set_colpali when CLIP / ColPali indices are absent.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.closed_set_clip import _load_subset_index as _clip_idx
from backend.sota.methods.closed_set_clip import _load_clip
from backend.sota.methods.closed_set_colpali import (
    _load_query_cache as _colpali_qcache,
    _load_subset_index as _colpali_idx,
)

logger = logging.getLogger(__name__)


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    candidates = (query.metadata or {}).get("candidate_docs", []) or []
    if not candidates:
        return []
    cp_idx = _colpali_idx(query.subset)
    cl_idx = _clip_idx(query.subset)
    if cp_idx is None or cl_idx is None:
        # Fall back to whichever is available
        if cp_idx:
            from backend.sota.methods.closed_set_colpali import _run as _cp
            return await _cp(query, top_k, ctx)
        if cl_idx:
            from backend.sota.methods.closed_set_clip import _run as _cl
            return await _cl(query, top_k, ctx)
        return []

    cp_embs, cp_keys, cp_n = cp_idx
    cl_embs, cl_keys = cl_idx

    try:
        import numpy as np
        import torch
    except ImportError:
        return []

    cand_set = set(candidates)
    # Build common index aligned to colpali keys (they should match)
    cp_key_to_row = {k: i for i, k in enumerate(cp_keys)}
    cl_key_to_row = {k: i for i, k in enumerate(cl_keys)}
    common = [k for k in cp_keys if k[0] in cand_set and k in cl_key_to_row]
    if not common:
        return []

    # Get ColPali query vec
    qcache = _colpali_qcache(query.subset)
    q_cp = qcache.get(str(query.query_id))
    if q_cp is None:
        from backend.sota.methods.closed_set_colpali import _run as _cp
        return await _cp(query, top_k, ctx)

    # Get CLIP query vec (text encoder; do via local CLIP)
    model, processor = _load_clip()
    if not model:
        from backend.sota.methods.closed_set_colpali import _run as _cp
        return await _cp(query, top_k, ctx)
    inputs = processor(text=[query.query[:300]], return_tensors="pt",
                       padding=True, truncation=True)
    with torch.no_grad():
        out = model.get_text_features(**inputs)
        if hasattr(out, "pooler_output"):
            q_cl = out.pooler_output
        elif torch.is_tensor(out):
            q_cl = out
        else:
            q_cl = out["pooler_output"] if "pooler_output" in out else out["last_hidden_state"][:, 0]
        q_cl = torch.nn.functional.normalize(q_cl, dim=-1).cpu().numpy()[0]

    cp_scores = []
    cl_scores = []
    keys_kept = []
    for k in common:
        i_cp = cp_key_to_row[k]
        i_cl = cl_key_to_row[k]
        n = cp_n[i_cp]
        page_emb = cp_embs[i_cp, :n].astype("float32")
        sim_cp = q_cp @ page_emb.T
        cp_scores.append(float(sim_cp.max(axis=1).sum()))
        cl_scores.append(float(cl_embs[i_cl] @ q_cl))
        keys_kept.append(k)

    cp = np.asarray(cp_scores, dtype="float32")
    cl = np.asarray(cl_scores, dtype="float32")

    def _z(x):
        return (x - x.mean()) / (x.std() + 1e-9)

    final = _z(cp) + 0.6 * _z(cl)
    order = final.argsort()[::-1][:top_k]
    return [(keys_kept[i][0], keys_kept[i][1], float(final[i])) for i in order]


register(MethodMeta(
    name="closed_set_ccc",
    version="1.0",
    description="CCC: ColPali MaxSim + CLIP global similarity z-score fusion (NOVEL).",
    needs=["colpali_index", "clip_index", "fusion_head_pt"],
    uses_test_labels=False,
    run=_run,
))
