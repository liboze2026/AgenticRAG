from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
from backend.services.evaluation import compute_recall_at_k, compute_mrr

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


@router.post("/experiments/evaluate")
async def evaluate(request: Request, body: EvalRequest):
    pipeline = request.app.state.pipeline_manager.pipeline
    recall_sums = {1: 0.0, 5: 0.0, 10: 0.0}
    mrr_sum = 0.0
    n = len(body.queries)
    for eq in body.queries:
        results = await pipeline.retrieve(eq.query, top_k=body.top_k)
        retrieved = [f"{r.document_id}:{r.page_number}" for r in results]
        relevant_set = set(eq.relevant)
        for k in recall_sums:
            recall_sums[k] += compute_recall_at_k(retrieved, relevant_set, k)
        mrr_sum += compute_mrr(retrieved, relevant_set)

    metrics = {
        "recall_at_k": {k: v / n for k, v in recall_sums.items()} if n > 0 else {},
        "mrr": mrr_sum / n if n > 0 else 0.0,
    }

    pipeline_config = request.app.state.pipeline_manager.get_current_config()
    exp_svc = request.app.state.experiment_service
    exp_id = exp_svc.record(
        pipeline_config=pipeline_config,
        metrics=metrics,
        total_queries=n,
        note=body.note,
    )

    return {
        "experiment_id": exp_id,
        "recall_at_k": metrics["recall_at_k"],
        "mrr": metrics["mrr"],
        "total_queries": n,
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
