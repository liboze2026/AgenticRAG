"""Phase 9 — Benchmark suite.

Runs a list of (query, relevant_pages) items through one or more retrieval
channels and reports MRR / Recall@5 / Recall@10 / Hit@1.

Channels supported (chosen per request):
* "colpali"  — main pipeline (whatever retriever the active config uses)
* "bm25"     — lab BM25 retriever (text-only)
* "rrf"      — fused via the lab hybrid service

Designed for small benchmarks the user can run live during a demo
(20-100 queries). For the real MMDocIR / VisDoMBench scale, run via the
existing scripts/qa_*.py harnesses; this endpoint targets demo-scale
visibility.

Each query has its own timeout — a single hang doesn't sink the run.
Channels are evaluated sequentially per query to avoid hammering the
remote worker; queries within a channel can be batched if needed but
default is serial for simplicity + reliability during demos.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List, Optional, Set, Tuple

from backend.lab.schemas import (
    BenchmarkChannelMetrics, BenchmarkPerQuery, BenchmarkQueryItem,
    BenchmarkResponse, GraphSeed,
)
from backend.models.schemas import RetrievalResult

logger = logging.getLogger(__name__)


SUPPORTED_CHANNELS = ("colpali", "bm25", "rrf")


def _eval_one(
    retrieved: List[RetrievalResult],
    relevant: List[GraphSeed],
) -> Tuple[float, float, float, float]:
    """Return (rr, recall@5, recall@10, hit@1)."""
    rel_set: Set[Tuple[str, int]] = {(r.document_id, r.page_number) for r in relevant}
    if not rel_set or not retrieved:
        return 0.0, 0.0, 0.0, 0.0

    ranked = [(r.document_id, r.page_number) for r in retrieved]
    rr = 0.0
    for i, key in enumerate(ranked):
        if key in rel_set:
            rr = 1.0 / (i + 1)
            break

    def recall_at(k: int) -> float:
        topk = set(ranked[:k])
        hits = len(topk & rel_set)
        return hits / len(rel_set)

    hit_1 = 1.0 if ranked[:1] and ranked[0] in rel_set else 0.0
    return rr, recall_at(5), recall_at(10), hit_1


async def _retrieve_channel(
    channel: str,
    pipeline,
    lab_bundle,
    query: str,
    top_k: int,
) -> List[RetrievalResult]:
    if channel == "colpali":
        bundle = await pipeline.retrieve(query, top_k=top_k)
        return bundle.results
    if channel == "bm25":
        # Lab hybrid maintains its own BM25 — sync first
        await lab_bundle.hybrid._ensure_bm25_synced()
        return await lab_bundle.hybrid.bm25.retrieve_text(query, top_k=top_k)
    if channel == "rrf":
        resp = await lab_bundle.hybrid.compare(
            pipeline, query=query, top_k=top_k, candidates=top_k * 2,
        )
        return next((c.results for c in resp.channels if c.channel == "rrf"), [])
    raise ValueError(f"Unsupported channel: {channel}")


async def _evaluate_query(
    channel: str,
    pipeline,
    lab_bundle,
    item: BenchmarkQueryItem,
    top_k: int,
    timeout_sec: float,
) -> Tuple[BenchmarkPerQuery, float]:
    """Run one query on one channel. Returns (metrics, latency_ms)."""
    t0 = time.perf_counter()
    try:
        retrieved = await asyncio.wait_for(
            _retrieve_channel(channel, pipeline, lab_bundle, item.query, top_k),
            timeout=timeout_sec,
        )
    except asyncio.TimeoutError:
        return BenchmarkPerQuery(
            query=item.query, channel=channel, retrieved=[],
            relevant=item.relevant_pages, note="timeout",
        ), (time.perf_counter() - t0) * 1000
    except Exception as e:
        logger.warning("benchmark %s query failed: %s", channel, e)
        return BenchmarkPerQuery(
            query=item.query, channel=channel, retrieved=[],
            relevant=item.relevant_pages,
            note=f"{type(e).__name__}: {e}",
        ), (time.perf_counter() - t0) * 1000

    latency = (time.perf_counter() - t0) * 1000
    rr, r5, r10, h1 = _eval_one(retrieved, item.relevant_pages)
    return BenchmarkPerQuery(
        query=item.query,
        channel=channel,
        retrieved=[GraphSeed(document_id=r.document_id, page_number=r.page_number)
                   for r in retrieved],
        relevant=item.relevant_pages,
        rr=rr, recall_at_5=r5, recall_at_10=r10, hit_at_1=h1,
        note="" if retrieved else "no retrieved results",
    ), latency


async def run_benchmark(
    pipeline,
    lab_bundle,
    items: List[BenchmarkQueryItem],
    channels: List[str],
    top_k: int = 10,
    timeout_per_query_sec: float = 30.0,
) -> BenchmarkResponse:
    """Run a benchmark over the requested channels."""
    timing: Dict[str, float] = {}
    if not items:
        return BenchmarkResponse(
            metrics=[], per_query=[], total_queries=0, channels=channels,
            note="无查询项 — 请先上传或提供 queries 列表",
        )

    bad_channels = [c for c in channels if c not in SUPPORTED_CHANNELS]
    if bad_channels:
        return BenchmarkResponse(
            metrics=[], per_query=[], total_queries=0, channels=channels,
            note=f"不支持的通道: {bad_channels}; 可选: {list(SUPPORTED_CHANNELS)}",
        )

    per_query: List[BenchmarkPerQuery] = []
    latency_by_channel: Dict[str, List[float]] = {c: [] for c in channels}

    t_run = time.perf_counter()
    for ch in channels:
        for item in items:
            metrics, latency = await _evaluate_query(
                ch, pipeline, lab_bundle, item,
                top_k=top_k, timeout_sec=timeout_per_query_sec,
            )
            per_query.append(metrics)
            latency_by_channel[ch].append(latency)
    timing["run_ms"] = (time.perf_counter() - t_run) * 1000

    # Aggregate
    metrics: List[BenchmarkChannelMetrics] = []
    for ch in channels:
        ch_results = [p for p in per_query if p.channel == ch]
        if not ch_results:
            continue
        n = len(ch_results)
        avg_latency = (
            sum(latency_by_channel[ch]) / n if latency_by_channel[ch] else 0.0
        )
        metrics.append(BenchmarkChannelMetrics(
            channel=ch,
            queries=n,
            mrr=sum(p.rr for p in ch_results) / n,
            recall_at_5=sum(p.recall_at_5 for p in ch_results) / n,
            recall_at_10=sum(p.recall_at_10 for p in ch_results) / n,
            hit_at_1=sum(p.hit_at_1 for p in ch_results) / n,
            avg_latency_ms=avg_latency,
        ))

    return BenchmarkResponse(
        metrics=metrics,
        per_query=per_query,
        total_queries=len(items),
        channels=channels,
        timing_ms=timing,
        note=f"已评测 {len(items)} 个问题 × {len(channels)} 通道",
    )
