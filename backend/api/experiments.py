import time
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
from backend.services.evaluation import compute_recall_at_k, compute_mrr
from backend.services.hard_negatives import augment_eval_set

router = APIRouter()


@router.get("/pipelines")
async def list_pipelines(request: Request):
    manager = request.app.state.pipeline_manager
    return {"available": manager.list_available(), "current": manager.get_current_config()}


class PipelineSwitch(BaseModel):
    processor: str
    document_encoder: str
    query_encoder: str
    retriever: str
    reranker: Optional[str] = None
    generator: str


@router.put("/pipelines/active")
async def switch_pipeline(request: Request, body: PipelineSwitch):
    manager = request.app.state.pipeline_manager
    manager.set_pipeline(body.model_dump())
    return {"status": "switched", "config": body.model_dump()}


class EvalQuery(BaseModel):
    query: str
    relevant: List[str]


class EvalRequest(BaseModel):
    queries: List[EvalQuery]
    top_k: int = 10
    note: str = ""
    dataset_id: Optional[int] = None


@router.post("/experiments/evaluate")
async def evaluate(request: Request, body: EvalRequest):
    manager = request.app.state.pipeline_manager
    pipeline = manager.pipeline
    exp_svc = request.app.state.experiment_service

    recall_sums = {1: 0.0, 5: 0.0, 10: 0.0}
    mrr_sum = 0.0
    timing_sums = {}
    per_query = []
    n = len(body.queries)

    for eq in body.queries:
        bundle = await pipeline.retrieve(eq.query, top_k=body.top_k)
        retrieved = [f"{r.document_id}:{r.page_number}" for r in bundle.results]
        relevant_set = set(eq.relevant)

        per_q_recall = {}
        for k in recall_sums:
            v = compute_recall_at_k(retrieved, relevant_set, k)
            recall_sums[k] += v
            per_q_recall[k] = v
        rr = compute_mrr(retrieved, relevant_set)
        mrr_sum += rr

        # Aggregate timing
        for tk, tv in bundle.timing.items():
            timing_sums[tk] = timing_sums.get(tk, 0.0) + tv

        per_query.append({
            "query": eq.query,
            "relevant": list(eq.relevant),
            "retrieved": retrieved,
            "rr": rr,
            "recall_at_k": per_q_recall,
            "timing_ms": bundle.timing,
        })

    metrics = {
        "recall_at_k": {k: v / n for k, v in recall_sums.items()} if n > 0 else {},
        "mrr": mrr_sum / n if n > 0 else 0.0,
        "total_queries": n,
        "avg_timing_ms": {k: v / n for k, v in timing_sums.items()} if n > 0 else {},
        "per_query": per_query,
    }

    # Snapshot the FULL effective pipeline config (not just the YAML names)
    full_config = pipeline.snapshot_config() if pipeline else {}
    yaml_config = manager.get_current_config() or {}
    snapshot = {"yaml": yaml_config, "effective": full_config}

    exp_id = exp_svc.record(
        pipeline_config=snapshot,
        metrics=metrics,
        total_queries=n,
        note=getattr(body, "note", ""),
        dataset_id=getattr(body, "dataset_id", None),
    )

    return {
        "experiment_id": exp_id,
        "recall_at_k": metrics["recall_at_k"],
        "mrr": metrics["mrr"],
        "total_queries": n,
        "avg_timing_ms": metrics["avg_timing_ms"],
    }


@router.get("/experiments/history")
async def list_experiments(request: Request, limit: int = 100):
    svc = request.app.state.experiment_service
    return svc.list_experiments(limit=limit)


@router.get("/experiments/{exp_id}")
async def get_experiment(request: Request, exp_id: int):
    svc = request.app.state.experiment_service
    exp = svc.get_experiment(exp_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp


@router.delete("/experiments/{exp_id}")
async def delete_experiment(request: Request, exp_id: int):
    svc = request.app.state.experiment_service
    ok = svc.delete_experiment(exp_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {"status": "deleted"}


class HardNegRequest(BaseModel):
    eval_data: List[dict]
    window: int = 2


@router.post("/experiments/hard_negatives")
async def generate_hard_negatives(request: Request, body: HardNegRequest):
    doc_svc = request.app.state.document_service
    docs = doc_svc.list_documents()
    all_doc_pages = {d.id: d.total_pages for d in docs if d.total_pages > 0}
    augmented = augment_eval_set(body.eval_data, all_doc_pages, window=body.window)
    return {"eval_data": augmented}
