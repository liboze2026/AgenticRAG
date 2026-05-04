"""Phase 7 — Feedback-driven supplementary retrieval.

Implements the "lightweight feedback controller" sketched in the proposal
section 3.1.3:

  Round 1 (initial)  → retrieve top-N
  GMM gate           → fit 2-component GMM on scores; assess "high-density"
                       cluster size and inter-cluster separation
  If converged       → done
  Else trigger one of these supplementary rounds (one per round):
    * neighbor_expand:    pull pages ±1 around current top hits
                          (rationale: cross-page continuations + figure-text
                          references; matches the "局部关系图" use case)
    * missing_caption:    when a top hit is a figure-heavy page but no
                          caption-like text appears, expand to the same
                          document with a caption-priority text query
    * missing_heading:    when no heading appears among top hits, run a
                          heading-only style query

Caps at `max_rounds` to avoid infinite loops. Always returns a structured
trace so the demo UI can show "round 1: initial → round 2: neighbor_expand
because high-cluster mass < 0.3" etc.

Composes with VISA at the end so the caller gets answer + bbox attribution
in one shot. Uses the main pipeline for retrieval and generation — no new
collections, no extra workers.
"""
from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Set, Tuple

from backend.lab.gmm import gmm_dynamic_topk, is_sklearn_available
from backend.lab.schemas import (
    EvidenceRegion, FeedbackResponse, FeedbackRound,
)
from backend.lab.visa import _autoinject_citations, _backfill_missing_citations, attribute_evidence
from backend.models.schemas import Answer, RetrievalResult

logger = logging.getLogger(__name__)


# Tunables — exposed so a future API request body can override them.
DEFAULT_TOP_K = 5
DEFAULT_CANDIDATES = 20
DEFAULT_MAX_ROUNDS = 3
DEFAULT_HIGH_CLUSTER_MIN_RATIO = 0.25     # below: trigger expansion
DEFAULT_LOW_GAP_MIN = 0.05                # below: clusters too close → low confidence


def _dedup_results(results: List[RetrievalResult]) -> List[RetrievalResult]:
    """Drop duplicate (doc_id, page) keeping highest score."""
    best: Dict[Tuple[str, int], RetrievalResult] = {}
    for r in results:
        key = (r.document_id, r.page_number)
        prev = best.get(key)
        if prev is None or r.score > prev.score:
            best[key] = r
    return sorted(best.values(), key=lambda r: r.score, reverse=True)


def _seen_pages(results: List[RetrievalResult]) -> Set[Tuple[str, int]]:
    return {(r.document_id, r.page_number) for r in results}


def _has_layout_with_type(results: List[RetrievalResult], et: str) -> bool:
    for r in results:
        if r.layout is None:
            continue
        for el in r.layout.elements:
            if el.element_type == et:
                return True
    return False


def _has_caption_text(results: List[RetrievalResult]) -> bool:
    """True when any element looks like a caption ('图N' / 'figure N' / '表N')."""
    import re
    cap_re = re.compile(r"^\s*(?:图|fig\.?|figure|表|table|tbl\.?)\s*[0-9]", re.IGNORECASE)
    for r in results:
        if r.layout is None:
            continue
        for el in r.layout.elements:
            t = (el.text or "").strip()
            if t and cap_re.match(t):
                return True
    return False


def _figure_heavy(results: List[RetrievalResult]) -> bool:
    """Heuristic: top page contains ≥ 1 figure but few text_blocks."""
    if not results:
        return False
    top = results[0]
    if top.layout is None:
        return False
    figs = sum(1 for el in top.layout.elements if el.element_type == "figure")
    texts = sum(1 for el in top.layout.elements if el.element_type == "text_block")
    return figs >= 1 and texts <= 2


def _gmm_signal(scores: List[float]) -> Tuple[bool, str]:
    """Return (converged, note).

    `converged` = True when the high-cluster has reasonable mass AND the
    two clusters are well-separated. False signals that we should trigger
    a supplementary round.
    """
    if not is_sklearn_available():
        return True, "sklearn 不可用 — 跳过 GMM 收敛判断"
    if len(scores) < 4:
        return True, f"候选数 {len(scores)} 太少 — 不触发反馈"
    try:
        from sklearn.mixture import GaussianMixture  # type: ignore
        import numpy as np
    except ImportError:
        return True, "sklearn 导入失败 — 跳过 GMM"
    rng = max(scores) - min(scores)
    if rng < 1e-6:
        return True, "分数全相同 — 无信息可判"
    try:
        X = np.array(scores).reshape(-1, 1)
        gmm = GaussianMixture(n_components=2, covariance_type="full",
                              random_state=42, max_iter=100, reg_covar=1e-6).fit(X)
        means = gmm.means_.flatten()
        weights = gmm.weights_.flatten()
        high_idx = int(np.argmax(means))
        high_weight = float(weights[high_idx])
        gap = float(abs(means[1] - means[0]))
        if high_weight < DEFAULT_HIGH_CLUSTER_MIN_RATIO:
            return False, (
                f"高分簇质量 {high_weight:.2f} < {DEFAULT_HIGH_CLUSTER_MIN_RATIO} "
                f"— 高分候选过少，触发补检索"
            )
        if gap < DEFAULT_LOW_GAP_MIN:
            return False, f"双峰间隔 {gap:.3f} 过小 — 候选区分度不足，触发补检索"
        return True, f"GMM 收敛 (高峰质量 {high_weight:.2f}, 间隔 {gap:.3f})"
    except Exception as e:
        return True, f"GMM 拟合失败 — 默认收敛 ({type(e).__name__})"


async def _retrieve_safe(pipeline, query: str, top_k: int) -> List[RetrievalResult]:
    try:
        bundle = await pipeline.retrieve(query, top_k=top_k)
        return bundle.results
    except Exception as e:
        logger.warning("feedback retrieve failed: %s", e)
        return []


async def _neighbor_expand(
    pipeline, query: str, seen: Set[Tuple[str, int]],
    current: List[RetrievalResult], top_k: int,
) -> List[RetrievalResult]:
    """Pull pages ±1 around the current top hits.

    Strategy: re-run the original query at higher depth and graft in any
    returned page that matches a neighbour target. For neighbours the deep
    retrieval missed, synthesize stub results (score=0) so the trace still
    shows the neighbour was considered.
    """
    if not current:
        return []
    target_pages: Set[Tuple[str, int]] = set()
    for r in current[:3]:
        if r.page_number > 1:
            target_pages.add((r.document_id, r.page_number - 1))
        target_pages.add((r.document_id, r.page_number + 1))
    target_pages -= seen
    if not target_pages:
        return []

    deep = await _retrieve_safe(pipeline, query, top_k=top_k * 4) if query else []
    extra: List[RetrievalResult] = []
    for r in deep:
        if (r.document_id, r.page_number) in target_pages:
            extra.append(r)
            target_pages.discard((r.document_id, r.page_number))

    # Synthesize stubs for neighbours not found by retrieval — score = 0.0
    # so they sit below real hits but stay visible in the trace.
    for d, p in list(target_pages)[:5]:
        extra.append(RetrievalResult(
            document_id=d, page_number=p, score=0.0,
            image_path="", layout=None,
        ))
    return extra


async def _typed_query(pipeline, augment: str, base_query: str, top_k: int) -> List[RetrievalResult]:
    """Run a query augmented with a hint string ('请关注图表' etc.)."""
    q = f"{augment} {base_query}".strip()
    return await _retrieve_safe(pipeline, q, top_k=top_k)


async def feedback_retrieve(
    pipeline,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    candidates: int = DEFAULT_CANDIDATES,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    do_generate: bool = True,
) -> FeedbackResponse:
    """End-to-end feedback loop: retrieve → judge → (expand)* → generate."""
    timing: Dict[str, float] = {}
    rounds: List[FeedbackRound] = []
    notes: List[str] = []

    if not pipeline:
        return FeedbackResponse(
            query=query, rounds=[], final_results=[], converged=False,
            note="主 pipeline 未就绪", timing_ms=timing,
        )

    # ---------------- Round 1: initial retrieval ----------------
    t0 = time.perf_counter()
    initial = await _retrieve_safe(pipeline, query, top_k=candidates)
    timing["round_1_retrieve_ms"] = (time.perf_counter() - t0) * 1000
    initial = _dedup_results(initial)

    # GMM-truncate initial set to a "stable top-k" using existing helper
    gmm_resp = gmm_dynamic_topk(query, initial, fixed_top_k=top_k)
    high_count = gmm_resp.dynamic_top_k

    rounds.append(FeedbackRound(
        round_index=1,
        trigger_reason="initial",
        query_used=query,
        candidate_count=len(initial),
        high_score_count=high_count,
        new_pages_added=len(initial),
        note=gmm_resp.note,
    ))

    if not initial:
        return FeedbackResponse(
            query=query, rounds=rounds, final_results=[], converged=False,
            note="初始检索无结果", timing_ms=timing,
        )

    # ---------------- Convergence judgement ----------------
    accumulated = list(initial)
    seen = _seen_pages(accumulated)

    for round_idx in range(2, max_rounds + 1):
        scores = [r.score for r in accumulated[: candidates]]
        converged, gmm_note = _gmm_signal(scores)
        # extra non-GMM signals based on layout content
        missing_caption = _figure_heavy(accumulated[:top_k]) and not _has_caption_text(accumulated[:top_k])
        missing_heading = not _has_layout_with_type(accumulated[:top_k], "heading")

        if converged and not missing_caption and not missing_heading:
            notes.append(f"R{round_idx - 1} 后收敛: {gmm_note}")
            break

        # Pick a trigger and run the corresponding supplementary action.
        if not converged:
            trigger = "low_density"
            extra = await _neighbor_expand(pipeline, query, seen, accumulated, top_k=top_k)
            note = f"GMM 触发: {gmm_note}; 新加邻接页 {len(extra)}"
        elif missing_caption:
            trigger = "missing_caption"
            extra = await _typed_query(pipeline, "图表 表格 标题", query, top_k=top_k)
            note = f"顶页含图但缺图注，启用图表关键词重检索 → +{len(extra)}"
        else:
            trigger = "missing_heading"
            extra = await _typed_query(pipeline, "章节 标题 段落", query, top_k=top_k)
            note = f"候选缺标题元素，启用标题关键词重检索 → +{len(extra)}"

        # merge new pages
        new_added = 0
        for r in extra:
            key = (r.document_id, r.page_number)
            if key in seen:
                continue
            seen.add(key)
            accumulated.append(r)
            new_added += 1
        accumulated = _dedup_results(accumulated)

        rounds.append(FeedbackRound(
            round_index=round_idx,
            trigger_reason=trigger,
            query_used=query,
            candidate_count=len(accumulated),
            high_score_count=sum(1 for r in accumulated[:candidates] if r.score >= scores[0] * 0.7) if scores else 0,
            new_pages_added=new_added,
            note=note,
        ))

        if new_added == 0:
            notes.append(f"R{round_idx} 无新页 — 提前结束补检索")
            break

    max_rounds_hit = len(rounds) >= max_rounds
    converged_flag = not max_rounds_hit
    if rounds and rounds[-1].trigger_reason == "initial":
        converged_flag = True

    final_results = accumulated[:top_k]

    # ---------------- Final generation + VISA attribution ----------------
    answer_text: Optional[str] = None
    regions: List[EvidenceRegion] = []
    if do_generate and final_results:
        try:
            t_gen = time.perf_counter()
            answer = await pipeline.generator.generate(query, final_results)
            timing["generate_ms"] = (time.perf_counter() - t_gen) * 1000
            # Reuse VISA citation handling so the trace is comparable to /lab/visa
            if answer.text and not _has_citation(answer.text):
                answer.text = _autoinject_citations(answer.text, len(final_results))
            else:
                answer.text = _backfill_missing_citations(answer.text, len(final_results))
            answer_text = answer.text
            regions, attr_note = attribute_evidence(answer, final_results)
            if attr_note:
                notes.append(attr_note)
        except Exception as e:
            logger.warning("feedback generate failed: %s", e)
            notes.append(f"生成失败: {type(e).__name__}")

    return FeedbackResponse(
        query=query,
        rounds=rounds,
        final_results=final_results,
        answer=answer_text,
        evidence_regions=regions,
        converged=converged_flag,
        max_rounds_hit=max_rounds_hit,
        timing_ms=timing,
        note="; ".join(notes),
    )


def _has_citation(text: str) -> bool:
    import re
    return bool(re.search(r"\[\d+\]", text or ""))
