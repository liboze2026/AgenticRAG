"""Background-task executor: orchestrates dataset × method matrix.

Per-query timeout 60 s; per-method timeout 30 min; per-run cap 6 h.
A method with ≥3 consecutive failures has its circuit opened for the
remainder of the run. Cancellation is cooperative.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List

from backend.sota.datasets import load_local_queries
from backend.sota.error_envelope import ErrorKind
from backend.sota.eval import (
    PerQueryResult, aggregate_metrics, bootstrap_ci, score_query,
)
from backend.sota.methods import MethodContext, get_method
from backend.sota.runs import RunRegistry
from backend.sota.schemas import (
    MethodResult, MethodStatus, MetricCell, RunConfig, RunStatus,
)

logger = logging.getLogger(__name__)

PER_QUERY_TIMEOUT_SEC = 60
PER_METHOD_TIMEOUT_SEC = 30 * 60
PER_RUN_TIMEOUT_SEC = 6 * 3600
CIRCUIT_BREAK_AFTER_N_FAILS = 3


class RunExecutor:
    def __init__(
        self,
        registry: RunRegistry,
        sota_data_root: str,
        pipeline,
        lab_bundle,
        qdrant_client,
        worker_client,
        corpus=None,
    ):
        self.registry = registry
        self.sota_data_root = sota_data_root
        self.pipeline = pipeline
        self.lab_bundle = lab_bundle
        self.qdrant_client = qdrant_client
        self.worker_client = worker_client
        self.corpus = corpus
        self._cancelled: Dict[str, bool] = {}

    def cancel(self, run_id: str) -> None:
        self._cancelled[run_id] = True

    def _is_cancelled(self, run_id: str) -> bool:
        return self._cancelled.get(run_id, False)

    async def execute(self, run_id: str, config: RunConfig) -> None:
        run_start = time.time()
        await self.registry.set_run_status(run_id, RunStatus.RUNNING)
        ctx = MethodContext(
            pipeline=self.pipeline, lab_bundle=self.lab_bundle,
            qdrant_client=self.qdrant_client, worker_client=self.worker_client,
            cancelled_flag=lambda: self._is_cancelled(run_id),
            extras={"corpus": self.corpus},
        )
        any_partial = False
        any_ok = False

        for method_name in config.methods:
            method_start = time.time()
            try:
                meta = get_method(method_name)
            except KeyError:
                await self.registry.upsert_method_result(run_id, MethodResult(
                    method=method_name, status=MethodStatus.SKIPPED,
                    duration_ms=0, error_kind="not_registered",
                ))
                continue

            consec_fail = 0
            method_status = MethodStatus.OK

            for subset in config.subsets:
                if self._is_cancelled(run_id):
                    method_status = MethodStatus.PARTIAL
                    break
                if time.time() - run_start > PER_RUN_TIMEOUT_SEC:
                    method_status = MethodStatus.PARTIAL
                    break

                queries = list(load_local_queries(
                    self.sota_data_root, subset,
                    limit=config.n_queries_per_subset,
                    split=config.split,
                ))
                if not queries:
                    await self.registry.append_error(
                        run_id, method_name, None,
                        ErrorKind.DATASET_MISSING.value,
                        f"no queries cached for subset {subset}",
                    )
                    continue

                per_query: List[PerQueryResult] = []
                for q in queries:
                    if self._is_cancelled(run_id):
                        break
                    if consec_fail >= CIRCUIT_BREAK_AFTER_N_FAILS:
                        method_status = MethodStatus.CIRCUIT_OPEN
                        break

                    t0 = time.time()
                    try:
                        ranked = await asyncio.wait_for(
                            meta.run(q, config.top_k, ctx),
                            timeout=PER_QUERY_TIMEOUT_SEC,
                        )
                        consec_fail = 0
                        ranked_pages = [(d, p) for (d, p, _s) in ranked]
                        r = score_query(q.gold_pages, ranked_pages)
                        r.query_id = q.query_id
                        r.latency_ms = int((time.time() - t0) * 1000)
                        per_query.append(r)
                        await self.registry.append_query_trace(run_id, {
                            "query_id": q.query_id, "subset": subset,
                            "method": method_name,
                            "ranked": ranked_pages[:10],
                            "gold": q.gold_pages,
                            "rr": r.rr, "hit_at_1": r.hit_at_1,
                            "hit_at_3": r.hit_at_3, "latency_ms": r.latency_ms,
                        })
                    except asyncio.TimeoutError:
                        consec_fail += 1
                        await self.registry.append_error(
                            run_id, method_name, q.query_id,
                            ErrorKind.METHOD_TIMEOUT.value,
                            f"query timed out after {PER_QUERY_TIMEOUT_SEC}s",
                        )
                    except Exception as e:
                        consec_fail += 1
                        await self.registry.append_error(
                            run_id, method_name, q.query_id,
                            ErrorKind.METHOD_FAILED.value,
                            f"{type(e).__name__}: {e}",
                        )

                if not per_query:
                    method_status = (
                        MethodStatus.PARTIAL if method_status == MethodStatus.OK else method_status
                    )
                    continue

                agg = aggregate_metrics(per_query)
                hit1_vals = [r.hit_at_1 for r in per_query]
                hit3_vals = [r.hit_at_3 for r in per_query]
                rr_vals = [r.rr for r in per_query]
                seed_base = abs(hash(run_id + method_name + subset)) & 0xFFFF
                lo1, hi1 = bootstrap_ci(hit1_vals, n_resamples=1000, seed=seed_base)
                lo3, hi3 = bootstrap_ci(hit3_vals, n_resamples=1000, seed=seed_base + 1)
                lo_rr, hi_rr = bootstrap_ci(rr_vals, n_resamples=1000, seed=seed_base + 2)
                n = int(agg["n"])

                for metric, value, lo, hi in (
                    ("recall@1", agg["recall@1"], lo1, hi1),
                    ("recall@3", agg["recall@3"], lo3, hi3),
                    ("mrr", agg["mrr"], lo_rr, hi_rr),
                    ("hit@1", agg["hit@1"], lo1, hi1),
                ):
                    await self.registry.append_metric(run_id, MetricCell(
                        method=method_name, subset=subset, metric=metric,
                        value=value, ci_low=lo, ci_high=hi, n_queries=n,
                    ))
                any_ok = True

            duration = int((time.time() - method_start) * 1000)
            await self.registry.upsert_method_result(run_id, MethodResult(
                method=method_name, status=method_status,
                duration_ms=duration, error_kind=None,
            ))
            if method_status != MethodStatus.OK:
                any_partial = True

        run_dur = int((time.time() - run_start) * 1000)
        if self._is_cancelled(run_id):
            final = RunStatus.CANCELLED
        elif any_ok and any_partial:
            final = RunStatus.PARTIAL
        elif any_ok:
            final = RunStatus.COMPLETED
        else:
            final = RunStatus.FAILED
        await self.registry.set_run_status(run_id, final, duration_ms=run_dur)
