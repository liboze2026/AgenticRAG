"""All /api/sota/* endpoints. Every handler returns HTTP 200 with envelope.

NOTE: do NOT add `from __future__ import annotations` — when a route is
wrapped by `wrap_response`, FastAPI resolves string annotations using the
wrapper's `__globals__` (error_envelope.py) which lacks Request, leading
to 422 errors. Keep annotations evaluated at import time.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Request
from pydantic import BaseModel, Field

from backend.sota.datasets import DatasetIntegrity, SUBSETS
from backend.sota.error_envelope import ErrorKind, SotaError, wrap_response
from backend.sota.methods import METHOD_REGISTRY
from backend.sota.schemas import RunConfig

logger = logging.getLogger(__name__)
router = APIRouter()


def _bundle(request: Request):
    bundle = getattr(request.app.state, "sota_bundle", None)
    if bundle is None:
        raise SotaError(ErrorKind.UNEXPECTED, "sota_bundle not initialized")
    return bundle


@router.get("/health")
@wrap_response
async def health(request: Request):
    bundle = _bundle(request)
    indexer_health = {}
    for name, idx in bundle.indexers.items():
        h = await idx.health()
        indexer_health[name] = {"ok": h.ok, "message": h.message, "points": h.points}
    return {
        "ok": True,
        "indexers": indexer_health,
        "methods": list(METHOD_REGISTRY.keys()),
    }


@router.get("/datasets")
@wrap_response
async def list_datasets(request: Request):
    bundle = _bundle(request)
    integ = DatasetIntegrity.scan(bundle.sota_data_root)
    return {"ok": True, "subsets": integ.subsets, "expected": list(SUBSETS)}


@router.get("/corpus")
@wrap_response
async def corpus_stats(request: Request):
    """Per-subset corpus health: text + OCR availability, doc count."""
    bundle = _bundle(request)
    return {"ok": True, "stats": bundle.corpus.stats()}


@router.post("/datasets/{subset}/check")
@wrap_response
async def check_dataset(subset: str, request: Request):
    bundle = _bundle(request)
    if subset not in SUBSETS:
        raise SotaError(ErrorKind.INVALID_CONFIG, f"unknown subset: {subset}")
    integ = DatasetIntegrity.scan(bundle.sota_data_root)
    return {"ok": True, "subset": subset, "info": integ.subsets.get(subset)}


@router.get("/methods")
@wrap_response
async def list_methods(request: Request):
    return {"ok": True, "methods": [
        {
            "name": m.name, "version": m.version,
            "description": m.description, "needs": m.needs,
        }
        for m in METHOD_REGISTRY.values()
    ]}


class CreateRunRequest(BaseModel):
    subsets: List[str] = Field(default_factory=lambda: list(SUBSETS))
    methods: List[str] = Field(default_factory=lambda: ["baseline_colpali", "baseline_bm25", "baseline_rrf"])
    top_k: int = 10
    n_queries_per_subset: Optional[int] = 50
    notes: str = ""


@router.post("/runs")
@wrap_response
async def create_run(req: CreateRunRequest, background_tasks: BackgroundTasks, request: Request):
    bundle = _bundle(request)
    for s in req.subsets:
        if s not in SUBSETS:
            raise SotaError(ErrorKind.INVALID_CONFIG, f"unknown subset: {s}")
    for m in req.methods:
        if m not in METHOD_REGISTRY:
            raise SotaError(ErrorKind.INVALID_CONFIG, f"unknown method: {m}")
    cfg = RunConfig(
        subsets=req.subsets, methods=req.methods, top_k=req.top_k,
        n_queries_per_subset=req.n_queries_per_subset, notes=req.notes,
    )
    run_id = await bundle.registry.create_run(cfg)
    background_tasks.add_task(bundle.executor.execute, run_id, cfg)
    return {"ok": True, "run_id": run_id}


@router.get("/runs")
@wrap_response
async def list_runs(request: Request, limit: int = 50):
    bundle = _bundle(request)
    rows = await bundle.registry.list_runs(limit=limit)
    return {"ok": True, "runs": [r.model_dump() for r in rows]}


@router.get("/runs/{run_id}")
@wrap_response
async def get_run(run_id: str, request: Request):
    bundle = _bundle(request)
    summary = await bundle.registry.get_run(run_id)
    return {"ok": True, "run": summary.model_dump()}


@router.post("/runs/{run_id}/cancel")
@wrap_response
async def cancel_run(run_id: str, request: Request):
    bundle = _bundle(request)
    bundle.executor.cancel(run_id)
    return {"ok": True}


@router.get("/leaderboard")
@wrap_response
async def leaderboard(request: Request):
    """Best (highest) value per (method, subset, metric) across all runs."""
    bundle = _bundle(request)
    rows = await bundle.registry.list_runs(limit=500)
    best: dict = {}
    for r in rows:
        for m in r.metrics:
            key = (m.method, m.subset, m.metric)
            if key not in best or m.value > best[key]["value"]:
                best[key] = {
                    "method": m.method, "subset": m.subset, "metric": m.metric,
                    "value": m.value, "ci_low": m.ci_low, "ci_high": m.ci_high,
                    "n_queries": m.n_queries, "run_id": r.id,
                }
    return {"ok": True, "rows": list(best.values())}
