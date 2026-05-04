"""Phase 3 — GMM dynamic top-k.

Fits a 2-component Gaussian Mixture on retrieval scores; the high-mean
component represents "relevant" candidates, the low-mean one represents
"noise". Dynamic top-k = number of candidates whose posterior probability
under the high cluster exceeds 0.5.

Returns histogram + GMM components for visualization, plus the truncated
result list. Falls back to fixed top-k when sklearn isn't installed or
when the score distribution is too small/uniform to fit.
"""
from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

from backend.lab.schemas import GmmComponent, GmmResponse, ScoreBucket
from backend.models.schemas import RetrievalResult

logger = logging.getLogger(__name__)


# --- sklearn (optional) --------------------------------------------------

try:
    from sklearn.mixture import GaussianMixture  # type: ignore
    import numpy as np                            # sklearn pulls numpy anyway
    _SKLEARN_OK = True
except ImportError:
    GaussianMixture = None
    np = None
    _SKLEARN_OK = False


def _build_histogram(scores: List[float], bins: int = 12) -> List[ScoreBucket]:
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-9:
        return [ScoreBucket(bin_start=lo, bin_end=lo, count=len(scores))]
    width = (hi - lo) / bins
    counts = [0] * bins
    for s in scores:
        idx = min(int((s - lo) / width), bins - 1)
        counts[idx] += 1
    return [
        ScoreBucket(bin_start=lo + i * width, bin_end=lo + (i + 1) * width, count=counts[i])
        for i in range(bins)
    ]


def _fixed_fallback(
    query: str,
    candidates: List[RetrievalResult],
    fixed_top_k: int,
    note: str,
) -> GmmResponse:
    scores = [r.score for r in candidates]
    return GmmResponse(
        query=query,
        fixed_top_k=fixed_top_k,
        dynamic_top_k=min(fixed_top_k, len(candidates)),
        cutoff_score=scores[fixed_top_k - 1] if scores and fixed_top_k <= len(scores) else 0.0,
        histogram=_build_histogram(scores),
        components=[],
        results=candidates[:fixed_top_k],
        note=note,
        timing_ms={"gmm_fit_ms": 0.0},
    )


def gmm_dynamic_topk(
    query: str,
    candidates: List[RetrievalResult],
    fixed_top_k: int = 5,
    min_k: int = 1,
    max_k_ratio: float = 0.8,
    posterior_threshold: float = 0.5,
) -> GmmResponse:
    """Fit GMM on `candidates` scores, return dynamic-truncated results.

    `min_k` ensures we always return at least one result.
    `max_k_ratio` caps dynamic_top_k at this fraction of len(candidates).
    """
    timing: Dict[str, float] = {}
    if not candidates:
        return GmmResponse(
            query=query, fixed_top_k=fixed_top_k, dynamic_top_k=0,
            cutoff_score=0.0, histogram=[], components=[], results=[],
            note="无候选 — 请检查检索器是否正常",
            timing_ms=timing,
        )

    if not _SKLEARN_OK:
        return _fixed_fallback(query, candidates, fixed_top_k,
                               note="sklearn 不可用 — 使用固定 top-k 退化")

    scores = [float(r.score) for r in candidates]
    if len(scores) < 4:
        return _fixed_fallback(query, candidates, fixed_top_k,
                               note=f"候选数 {len(scores)} 太少，GMM 拟合不稳定 — 退化")

    score_range = max(scores) - min(scores)
    if score_range < 1e-6:
        return _fixed_fallback(query, candidates, fixed_top_k,
                               note="分数全部相等 — 分布无信息，退化")

    try:
        t0 = time.perf_counter()
        X = np.array(scores).reshape(-1, 1)
        gmm = GaussianMixture(
            n_components=2, covariance_type="full",
            random_state=42, max_iter=100, reg_covar=1e-6,
        )
        gmm.fit(X)
        timing["gmm_fit_ms"] = (time.perf_counter() - t0) * 1000

        means = gmm.means_.flatten()
        covs = gmm.covariances_.flatten()
        weights = gmm.weights_.flatten()

        high_idx = int(np.argmax(means))
        low_idx = 1 - high_idx

        # Posterior under the high component
        posterior = gmm.predict_proba(X)[:, high_idx]
        # Indices of candidates assigned to the high cluster
        chosen = [i for i in range(len(scores)) if posterior[i] >= posterior_threshold]
        # Apply min/max bounds
        max_k = max(min_k, int(len(scores) * max_k_ratio))
        if not chosen:
            dynamic_k = min_k
        else:
            dynamic_k = min(max(len(chosen), min_k), max_k)

        # Determine cutoff score (boundary between included/excluded)
        sorted_scores = sorted(scores, reverse=True)
        cutoff = sorted_scores[dynamic_k - 1] if dynamic_k <= len(sorted_scores) else sorted_scores[-1]

        return GmmResponse(
            query=query,
            fixed_top_k=fixed_top_k,
            dynamic_top_k=dynamic_k,
            cutoff_score=float(cutoff),
            histogram=_build_histogram(scores),
            components=[
                GmmComponent(
                    mean=float(means[low_idx]),
                    variance=float(covs[low_idx]),
                    weight=float(weights[low_idx]),
                ),
                GmmComponent(
                    mean=float(means[high_idx]),
                    variance=float(covs[high_idx]),
                    weight=float(weights[high_idx]),
                ),
            ],
            results=candidates[:dynamic_k],
            timing_ms=timing,
            note=(
                f"GMM 选取 {dynamic_k} 页 (固定 top-k={fixed_top_k}); "
                f"高峰 μ={means[high_idx]:.3f} σ²={covs[high_idx]:.3f}, "
                f"低峰 μ={means[low_idx]:.3f}"
            ),
        )
    except Exception as e:
        logger.warning("GMM fit failed: %s", e)
        return _fixed_fallback(query, candidates, fixed_top_k,
                               note=f"GMM 拟合失败: {type(e).__name__} — 退化")


async def gmm_query(pipeline, query: str, top_k: int = 5, candidates: int = 20) -> GmmResponse:
    """Retrieve `candidates` deep, fit GMM, return dynamic top-k subset."""
    bundle = await pipeline.retrieve(query, top_k=candidates)
    return gmm_dynamic_topk(query, bundle.results, fixed_top_k=top_k)


def is_sklearn_available() -> bool:
    return _SKLEARN_OK
