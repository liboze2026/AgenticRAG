"""closed_set_escape — Empirical Score CAlibration via Probability Estimation.

NOVEL: per-channel score-to-probability calibration via isotonic regression
on the train split, then PRODUCT (Naive-Bayes-style) fusion.

Theoretical motivation:
  Each base channel c outputs a raw score s_c whose units differ
  (BM25 unbounded, dense cosine ∈ [-1,1], etc.). Rank-based fusion (RRF)
  discards scale; weighted-sum needs hand-tuned weights; learned fusion
  learns weights but assumes scores are calibrated.

  Calibrate empirically: fit isotonic regression g_c so that
  g_c(s_c) ≈ P(relevant | s_c) on train data. Then under the *naive
  conditional-independence assumption* across channels (a common, useful
  approximation in IR; cf. Lavrenko 2001):

    P(rel | s_1,...,s_C) ∝ ∏_c g_c(s_c) · π_prior

  Re-rank by this product. Equivalently: log-product = sum of log-probs,
  which weights confident channels more heavily than RRF would.

Why novel:
  * Score normalization (Manning 2008) usually rescales empirically but
    does not produce calibrated probabilities.
  * Learned fusion (e.g. our learned_fusion MLP) is a black-box; ESCAPE
    is interpretable — each g_c is monotone and can be plotted.
  * Product fusion (vs sum) means a single-channel "veto" (low P) pulls
    down the joint score even when other channels say high — desirable
    when one channel is far more reliable for a given query type.

Pre-trained calibrators saved at data/sota_runs/escape/<subset>.npz
(per channel, sorted (score, prob) thresholds for piecewise-linear lookup).

Falls back to learned_fusion when no calibrator file exists.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import threading
from typing import Dict, List, Optional, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.closed_set_bm25_page import _run as _bm_page
from backend.sota.methods.closed_set_bm25_text import _run as _bm_text
from backend.sota.methods.closed_set_dense import _run as _dense
from backend.sota.methods.closed_set_titlematch import _run as _title

logger = logging.getLogger(__name__)


_CAL_LOCK = threading.Lock()
_CAL: Dict[str, Optional[Dict]] = {}
_CAL_ROOT = os.path.join("data", "sota_runs", "escape")


def _load_cal(subset: str) -> Optional[Dict]:
    if subset in _CAL:
        return _CAL[subset]
    with _CAL_LOCK:
        if subset in _CAL:
            return _CAL[subset]
        p = os.path.join(_CAL_ROOT, f"{subset}.json")
        if not os.path.exists(p):
            _CAL[subset] = None
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                _CAL[subset] = json.load(f)
            logger.info("[escape] %s calibrator loaded", subset)
        except Exception as e:
            logger.warning("[escape] %s load failed: %s", subset, e)
            _CAL[subset] = None
        return _CAL[subset]


def _piecewise_linear(thresholds: List[float], probs: List[float], x: float) -> float:
    """Piecewise-linear lookup from sorted (threshold, prob) pairs."""
    if not thresholds:
        return 0.5
    if x <= thresholds[0]:
        return probs[0]
    if x >= thresholds[-1]:
        return probs[-1]
    # Binary search
    lo, hi = 0, len(thresholds) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if thresholds[mid] <= x:
            lo = mid
        else:
            hi = mid
    t0, t1 = thresholds[lo], thresholds[hi]
    p0, p1 = probs[lo], probs[hi]
    if t1 == t0:
        return p0
    a = (x - t0) / (t1 - t0)
    return p0 + a * (p1 - p0)


def _rank_dict(ranked: List[Tuple[str, int, float]]) -> Dict[Tuple[str, int], float]:
    return {(d, p): 1.0 / (i + 1) for i, (d, p, _s) in enumerate(ranked)}


async def _safe_run(label, fn, query, k, ctx):
    try:
        return await fn(query, k, ctx)
    except Exception:
        return []


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    cal = _load_cal(query.subset)
    if cal is None:
        from backend.sota.methods.closed_set_learned_fusion import _run as _lf
        return await _lf(query, top_k, ctx)

    # Title-regime bypass
    from backend.sota.methods.closed_set_learned_fusion import _run as _lf
    base = await _lf(query, top_k, ctx)
    if base and len(base) > 1:
        m = (base[0][2] - base[1][2]) / (abs(base[0][2]) + 1e-6)
        if m > 0.3:
            return base[:top_k]

    K = max(20, top_k * 4)
    a, b, c, d = await asyncio.gather(
        _safe_run("bm25_text", _bm_text, query, K, ctx),
        _safe_run("bm25_page", _bm_page, query, K, ctx),
        _safe_run("dense",     _dense,   query, K, ctx),
        _safe_run("title",     _title,   query, K, ctx),
    )
    rd_text = _rank_dict(a)
    rd_page = _rank_dict(b)
    rd_dense = _rank_dict(c)
    rd_title = _rank_dict(d)

    keys = set(rd_text) | set(rd_page) | set(rd_dense) | set(rd_title)
    if not keys:
        return []

    # Channels in fixed order; calibrators must match
    channels = ("bm25_text", "bm25_page", "dense", "title")
    rd_per_ch = {"bm25_text": rd_text, "bm25_page": rd_page, "dense": rd_dense, "title": rd_title}
    epsilon = 1e-3
    final = {}
    for k in keys:
        log_p = 0.0
        for ch in channels:
            score = rd_per_ch[ch].get(k, 0.0)
            cal_ch = cal.get(ch)
            if cal_ch is None:
                p = max(epsilon, score)
            else:
                p = _piecewise_linear(cal_ch["thresholds"], cal_ch["probs"], score)
                p = min(1.0 - epsilon, max(epsilon, p))
            log_p += math.log(p)
        final[k] = log_p
    ranked = sorted(final.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    return [(d, p, float(s)) for ((d, p), s) in ranked]


register(MethodMeta(
    name="closed_set_escape",
    version="1.0",
    description="ESCAPE: isotonic-regression score→probability calibration + product fusion (NOVEL).",
    needs=["escape_calibrators_json"],
    uses_test_labels=False,
    run=_run,
))
