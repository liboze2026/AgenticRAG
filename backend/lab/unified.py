"""Phase 8 — Unified orchestration.

Combines all lab features into one configurable pipeline:

    request flags  →  stages run in this order
    use_hybrid     →  BM25 + ColPali + RRF (replaces single-channel retrieval)
    use_gmm        →  dynamic top-k truncation
    use_feedback   →  feedback-driven supplementary retrieval (uses pipeline)
    do_generate    →  call generator (citation prompt)
    use_visa       →  bbox attribution on the answer
    use_region     →  also fetch region-level hits for the same query
    use_graph      →  build local relation graph for final pages

Every stage is optional and isolated: if one stage fails, the response
records the failure as a non-OK stage but continues with the remaining
stages so the demo never goes blank. The legacy /api/query path is
untouched.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple

from backend.lab.feedback import _has_citation
from backend.lab.gmm import gmm_dynamic_topk
from backend.lab.graph import LabGraphService
from backend.lab.schemas import (
    EvidenceRegion, GraphEdge, GraphNode, RegionHit,
    UnifiedResponse, UnifiedStage,
)
from backend.lab.visa import (
    _autoinject_citations, _backfill_missing_citations, attribute_evidence,
    _VISA_QUERY_PREFIX,
)
from backend.models.schemas import RetrievalResult

logger = logging.getLogger(__name__)


def _dedup(results: List[RetrievalResult]) -> List[RetrievalResult]:
    best: Dict[Tuple[str, int], RetrievalResult] = {}
    for r in results:
        key = (r.document_id, r.page_number)
        prev = best.get(key)
        if prev is None or r.score > prev.score:
            best[key] = r
    return sorted(best.values(), key=lambda r: r.score, reverse=True)


class LabUnifiedService:
    """One handler that orchestrates every lab feature for one query.

    Holds references to the lab bundle's component services + the main
    pipeline. Stays decoupled: this class never imports route handlers,
    and route handlers never run business logic — they just call run().
    """

    def __init__(self, lab_bundle, qdrant_client, region_service=None):
        self.lab_bundle = lab_bundle
        self.qdrant = qdrant_client
        self.region_service = region_service
        self.graph_service = LabGraphService(qdrant_client=qdrant_client)

    async def _hybrid_stage(
        self, pipeline, query: str, top_k: int, candidates: int,
    ) -> Tuple[UnifiedStage, List[RetrievalResult]]:
        t0 = time.perf_counter()
        try:
            resp = await self.lab_bundle.hybrid.compare(
                pipeline, query=query, top_k=top_k,
                rrf_k=60, candidates=candidates,
            )
            fused = next((c.results for c in resp.channels if c.channel == "rrf"), [])
            stage = UnifiedStage(
                name="hybrid", ok=True,
                timing_ms=(time.perf_counter() - t0) * 1000,
                summary={
                    "channels": [c.channel for c in resp.channels],
                    "channel_counts": {c.channel: len(c.results) for c in resp.channels},
                    "fused": len(fused),
                },
                note="RRF 融合通道作为后续输入",
            )
            return stage, fused
        except Exception as e:
            logger.exception("unified hybrid stage failed")
            return UnifiedStage(
                name="hybrid", ok=False,
                timing_ms=(time.perf_counter() - t0) * 1000,
                note=f"双通道失败: {type(e).__name__}: {e}",
            ), []

    async def _plain_retrieve_stage(
        self, pipeline, query: str, top_k: int,
    ) -> Tuple[UnifiedStage, List[RetrievalResult]]:
        t0 = time.perf_counter()
        try:
            bundle = await pipeline.retrieve(query, top_k=top_k)
            return UnifiedStage(
                name="retrieve", ok=True,
                timing_ms=(time.perf_counter() - t0) * 1000,
                summary={"results": len(bundle.results)},
                note="主管道单通道检索",
            ), bundle.results
        except Exception as e:
            logger.exception("unified plain retrieve failed")
            return UnifiedStage(
                name="retrieve", ok=False,
                timing_ms=(time.perf_counter() - t0) * 1000,
                note=f"主管道检索失败: {type(e).__name__}: {e}",
            ), []

    def _gmm_stage(
        self, query: str, candidates: List[RetrievalResult], top_k: int,
    ) -> Tuple[UnifiedStage, List[RetrievalResult]]:
        t0 = time.perf_counter()
        try:
            resp = gmm_dynamic_topk(query, candidates, fixed_top_k=top_k)
            return UnifiedStage(
                name="gmm", ok=True,
                timing_ms=(time.perf_counter() - t0) * 1000,
                summary={
                    "fixed_top_k": resp.fixed_top_k,
                    "dynamic_top_k": resp.dynamic_top_k,
                    "cutoff_score": resp.cutoff_score,
                },
                note=resp.note,
            ), resp.results
        except Exception as e:
            logger.exception("unified gmm stage failed")
            return UnifiedStage(
                name="gmm", ok=False,
                timing_ms=(time.perf_counter() - t0) * 1000,
                note=f"GMM 失败: {type(e).__name__}: {e}",
            ), candidates[:top_k]

    async def _feedback_stage(
        self, pipeline, query: str, candidates: List[RetrievalResult], top_k: int,
    ) -> Tuple[UnifiedStage, List[RetrievalResult]]:
        """Lite version of feedback module — works on already-retrieved pool.

        Goal: detect low-density via GMM and pull ±1 neighbours organically.
        Avoids re-running heavy retrieval since unified already paid for one.
        """
        t0 = time.perf_counter()
        try:
            from backend.lab.feedback import _gmm_signal, _figure_heavy, _has_caption_text
            scores = [r.score for r in candidates[:20]]
            converged, note = _gmm_signal(scores)
            missing_caption = _figure_heavy(candidates[:top_k]) and not _has_caption_text(candidates[:top_k])
            triggered = (not converged) or missing_caption
            new_pages = 0
            merged = list(candidates)
            seen = {(r.document_id, r.page_number) for r in merged}

            if triggered:
                # Only neighbour expansion in unified mode (cheap, no re-query).
                for r in candidates[:3]:
                    for off in (-1, 1):
                        np_ = r.page_number + off
                        if np_ < 1:
                            continue
                        key = (r.document_id, np_)
                        if key in seen:
                            continue
                        seen.add(key)
                        merged.append(RetrievalResult(
                            document_id=r.document_id, page_number=np_,
                            score=max(0.0, r.score * 0.6),
                            image_path="", layout=None,
                        ))
                        new_pages += 1

            merged = _dedup(merged)[:top_k]
            return UnifiedStage(
                name="feedback", ok=True,
                timing_ms=(time.perf_counter() - t0) * 1000,
                summary={
                    "triggered": triggered,
                    "neighbours_added": new_pages,
                },
                note=f"{note}; 邻接扩展 +{new_pages}" if triggered else note,
            ), merged
        except Exception as e:
            logger.exception("unified feedback stage failed")
            return UnifiedStage(
                name="feedback", ok=False,
                timing_ms=(time.perf_counter() - t0) * 1000,
                note=f"反馈控制失败: {type(e).__name__}: {e}",
            ), candidates[:top_k]

    async def _generate_stage(
        self, pipeline, query: str, sources: List[RetrievalResult],
    ) -> Tuple[UnifiedStage, Optional[str]]:
        t0 = time.perf_counter()
        if not sources:
            return UnifiedStage(
                name="generate", ok=False,
                timing_ms=0.0, note="无证据可生成",
            ), None
        try:
            answer = await pipeline.generator.generate(_VISA_QUERY_PREFIX + query, sources)
            text = answer.text or ""
            if text and not _has_citation(text):
                text = _autoinject_citations(text, len(sources))
            else:
                text = _backfill_missing_citations(text, len(sources))
            answer.text = text
            return UnifiedStage(
                name="generate", ok=True,
                timing_ms=(time.perf_counter() - t0) * 1000,
                summary={"length": len(text)},
                note="已生成答案",
            ), text
        except Exception as e:
            logger.exception("unified generate stage failed")
            return UnifiedStage(
                name="generate", ok=False,
                timing_ms=(time.perf_counter() - t0) * 1000,
                note=f"生成失败: {type(e).__name__}: {e}",
            ), None

    def _visa_stage(
        self, answer_text: Optional[str], sources: List[RetrievalResult],
    ) -> Tuple[UnifiedStage, List[EvidenceRegion]]:
        t0 = time.perf_counter()
        if not answer_text:
            return UnifiedStage(name="visa", ok=False, note="无答案，跳过 VISA"), []
        try:
            from backend.models.schemas import Answer
            answer = Answer(text=answer_text, sources=sources)
            regions, note = attribute_evidence(answer, sources)
            return UnifiedStage(
                name="visa", ok=True,
                timing_ms=(time.perf_counter() - t0) * 1000,
                summary={"regions": len(regions)},
                note=note or f"已生成 {len(regions)} 条 bbox",
            ), regions
        except Exception as e:
            logger.exception("unified visa stage failed")
            return UnifiedStage(
                name="visa", ok=False,
                timing_ms=(time.perf_counter() - t0) * 1000,
                note=f"VISA 失败: {type(e).__name__}: {e}",
            ), []

    async def _region_stage(self, query: str, top_k: int) -> Tuple[UnifiedStage, List[RegionHit]]:
        t0 = time.perf_counter()
        if self.region_service is None:
            return UnifiedStage(name="region", ok=False, note="区域服务未挂载"), []
        try:
            resp = await self.region_service.query(query, top_k=top_k)
            return UnifiedStage(
                name="region", ok=True,
                timing_ms=(time.perf_counter() - t0) * 1000,
                summary={"hits": len(resp.hits)},
                note=resp.note,
            ), resp.hits
        except Exception as e:
            logger.exception("unified region stage failed")
            return UnifiedStage(
                name="region", ok=False,
                timing_ms=(time.perf_counter() - t0) * 1000,
                note=f"区域检索失败: {type(e).__name__}: {e}",
            ), []

    async def _graph_stage(
        self, query: str, sources: List[RetrievalResult],
    ) -> Tuple[UnifiedStage, List[GraphNode], List[GraphEdge]]:
        t0 = time.perf_counter()
        try:
            seeds = [(r.document_id, r.page_number) for r in sources]
            if not seeds:
                return UnifiedStage(name="graph", ok=False, note="无种子页"), [], []
            nodes, edges, notes = await self.graph_service.build_for_pages(
                seeds, include_neighbours=True,
            )
            return UnifiedStage(
                name="graph", ok=True,
                timing_ms=(time.perf_counter() - t0) * 1000,
                summary={"nodes": len(nodes), "edges": len(edges),
                         "edge_types": _count_edge_types(edges)},
                note="; ".join(notes) if notes else f"{len(nodes)} 节点 / {len(edges)} 边",
            ), nodes, edges
        except Exception as e:
            logger.exception("unified graph stage failed")
            return UnifiedStage(
                name="graph", ok=False,
                timing_ms=(time.perf_counter() - t0) * 1000,
                note=f"关系图失败: {type(e).__name__}: {e}",
            ), [], []

    async def run(
        self,
        pipeline,
        query: str,
        top_k: int = 5,
        candidates: int = 20,
        use_hybrid: bool = True,
        use_gmm: bool = False,
        use_feedback: bool = False,
        use_visa: bool = True,
        use_region: bool = False,
        use_graph: bool = False,
        do_generate: bool = True,
    ) -> UnifiedResponse:
        timing: Dict[str, float] = {}
        stages: List[UnifiedStage] = []

        t_total = time.perf_counter()

        # 1. Retrieval (hybrid or plain)
        if use_hybrid:
            stage, results = await self._hybrid_stage(pipeline, query, top_k=candidates, candidates=candidates)
        else:
            stage, results = await self._plain_retrieve_stage(pipeline, query, top_k=candidates)
        stages.append(stage)
        results = _dedup(results)

        # 2. GMM truncation (optional)
        if use_gmm and results:
            stage, results = self._gmm_stage(query, results, top_k=top_k)
            stages.append(stage)
        else:
            results = results[:top_k]

        # 3. Feedback expansion (optional)
        if use_feedback and results:
            stage, results = await self._feedback_stage(pipeline, query, results, top_k=top_k)
            stages.append(stage)

        # 4. Region-level retrieval (optional, parallelizable)
        region_hits: List[RegionHit] = []
        graph_nodes: List[GraphNode] = []
        graph_edges: List[GraphEdge] = []

        # Run region + graph in parallel since they're independent of each other.
        sub_tasks = []
        if use_region:
            sub_tasks.append(self._region_stage(query, top_k=top_k))
        if use_graph:
            sub_tasks.append(self._graph_stage(query, results))
        if sub_tasks:
            sub_results = await asyncio.gather(*sub_tasks, return_exceptions=True)
            for r in sub_results:
                if isinstance(r, BaseException):
                    stages.append(UnifiedStage(name="parallel", ok=False, note=str(r)))
                    continue
                # Each sub-result is the appropriate tuple shape
                stage, *rest = r
                stages.append(stage)
                if stage.name == "region":
                    region_hits = rest[0]
                elif stage.name == "graph":
                    graph_nodes, graph_edges = rest[0], rest[1]

        # 5. Generation (optional)
        answer_text: Optional[str] = None
        if do_generate and results:
            stage, answer_text = await self._generate_stage(pipeline, query, results)
            stages.append(stage)

        # 6. VISA attribution (depends on answer + sources)
        evidence_regions: List[EvidenceRegion] = []
        if use_visa and answer_text:
            stage, evidence_regions = self._visa_stage(answer_text, results)
            stages.append(stage)

        timing["total_ms"] = (time.perf_counter() - t_total) * 1000

        return UnifiedResponse(
            query=query,
            stages=stages,
            final_results=results,
            answer=answer_text,
            evidence_regions=evidence_regions,
            graph_nodes=graph_nodes,
            graph_edges=graph_edges,
            region_hits=region_hits,
            timing_ms=timing,
            note="所有阶段已执行 (失败的阶段 ok=false 详见 stages)",
        )


def _count_edge_types(edges: List[GraphEdge]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for e in edges:
        out[e.edge_type] = out.get(e.edge_type, 0) + 1
    return out
