"""All /api/lab/* endpoints — single router mounted under /api/lab."""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

from backend.lab.benchmark import run_benchmark
from backend.lab.feedback import feedback_retrieve
from backend.lab.gmm import gmm_query
from backend.lab.health import collect_lab_health
from backend.lab.hybrid import LabHybridService
from backend.lab.region import LabRegionService
from backend.lab.schemas import (
    BenchmarkQueryItem, BenchmarkResponse,
    FeedbackResponse, GmmResponse, GraphResponse,
    HybridCompareResponse, LabHealth, RegionResponse,
    UnifiedResponse, VisaResponse,
)
from backend.lab.visa import visa_query

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models (pydantic) — not in schemas.py because they are HTTP-shaped
# ---------------------------------------------------------------------------

class HybridRequest(BaseModel):
    query: str
    top_k: int = Field(5, ge=1, le=50)
    candidates: int = Field(20, ge=1, le=100)
    rrf_k: int = 60
    do_generate: bool = False


class VisaRequest(BaseModel):
    query: str
    top_k: int = Field(5, ge=1, le=50)


class GmmRequest(BaseModel):
    query: str
    top_k: int = Field(5, ge=1, le=50)
    candidates: int = Field(20, ge=4, le=100)


class RegionQueryRequest(BaseModel):
    query: str
    top_k: int = Field(8, ge=1, le=30)


class GraphRequest(BaseModel):
    query: str
    top_k: int = Field(5, ge=1, le=20)
    include_neighbours: bool = True


class FeedbackRequest(BaseModel):
    query: str
    top_k: int = Field(5, ge=1, le=20)
    candidates: int = Field(20, ge=4, le=100)
    max_rounds: int = Field(3, ge=1, le=6)
    do_generate: bool = True


class UnifiedRequest(BaseModel):
    query: str
    top_k: int = Field(5, ge=1, le=20)
    candidates: int = Field(20, ge=4, le=100)
    use_hybrid: bool = True
    use_gmm: bool = False
    use_feedback: bool = False
    use_visa: bool = True
    use_region: bool = False
    use_graph: bool = False
    do_generate: bool = True


class BenchmarkRequest(BaseModel):
    queries: List[BenchmarkQueryItem]
    channels: List[str] = Field(default_factory=lambda: ["colpali"])
    top_k: int = Field(10, ge=1, le=50)
    timeout_per_query_sec: float = Field(30.0, ge=1.0, le=120.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_query(q: str) -> str:
    q = (q or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="问题不能为空")
    if len(q) > 4000:
        raise HTTPException(status_code=400, detail="问题过长 (>4000 字符)")
    return q


def _get_pipeline(request: Request):
    pm = getattr(request.app.state, "pipeline_manager", None)
    if pm is None or pm.pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="主 pipeline 未就绪 — 请检查 worker / Qdrant 是否在线",
        )
    return pm.pipeline


def _get_lab(request: Request):
    """Return the LabBundle from app.state, or 503."""
    lab = getattr(request.app.state, "lab_bundle", None)
    if lab is None:
        raise HTTPException(status_code=503, detail="Lab 模块未挂载")
    return lab


# ---------------------------------------------------------------------------
# Phase 1 — Hybrid compare
# ---------------------------------------------------------------------------

@router.post("/hybrid", response_model=HybridCompareResponse)
async def hybrid_compare(request: Request, body: HybridRequest):
    query = _validate_query(body.query)
    pipeline = _get_pipeline(request)
    lab = _get_lab(request)
    try:
        resp = await lab.hybrid.compare(
            pipeline, query=query, top_k=body.top_k,
            rrf_k=body.rrf_k, candidates=body.candidates,
        )
    except Exception as e:
        logger.exception("hybrid compare crashed")
        raise HTTPException(status_code=500, detail=f"双通道对比失败: {type(e).__name__}: {e}")

    if body.do_generate:
        fused = next((c.results for c in resp.channels if c.channel == "rrf"), [])
        resp.answer = await lab.hybrid.generate_from_fused(pipeline, query, fused)
    return resp


# ---------------------------------------------------------------------------
# Phase 2 — VISA attribution
# ---------------------------------------------------------------------------

@router.post("/visa", response_model=VisaResponse)
async def visa_attribution(request: Request, body: VisaRequest):
    query = _validate_query(body.query)
    pipeline = _get_pipeline(request)
    return await visa_query(pipeline, query=query, top_k=body.top_k)


# ---------------------------------------------------------------------------
# Phase 3 — GMM dynamic top-k
# ---------------------------------------------------------------------------

@router.post("/gmm", response_model=GmmResponse)
async def gmm_dynamic(request: Request, body: GmmRequest):
    query = _validate_query(body.query)
    pipeline = _get_pipeline(request)
    try:
        return await gmm_query(pipeline, query=query, top_k=body.top_k, candidates=body.candidates)
    except Exception as e:
        logger.exception("gmm crashed")
        raise HTTPException(status_code=500, detail=f"GMM 流程失败: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Phase 4 — Region-level retrieval
# ---------------------------------------------------------------------------

@router.post("/region/query", response_model=RegionResponse)
async def region_query(request: Request, body: RegionQueryRequest):
    query = _validate_query(body.query)
    lab = _get_lab(request)
    if lab.region is None:
        raise HTTPException(status_code=503, detail="区域级检索服务未就绪")
    return await lab.region.query(query, top_k=body.top_k)


@router.post("/region/index/{doc_id}")
async def region_index_one(
    request: Request, doc_id: str,
    background_tasks: BackgroundTasks,
    sync: bool = False,
):
    """Trigger region indexing for one document.

    Default (sync=False): returns 202 immediately + runs in background.
    Use GET /region/status/{doc_id} to poll progress.

    sync=true: blocks until completion. Only safe for tiny docs.
    """
    lab = _get_lab(request)
    if lab.region is None:
        raise HTTPException(status_code=503, detail="区域级检索服务未就绪")
    if sync:
        try:
            return await lab.region.index_document(doc_id)
        except Exception as e:
            logger.exception("region index failed")
            raise HTTPException(status_code=500, detail=f"区域索引失败: {type(e).__name__}: {e}")

    # Async path: queue job, return 202 immediately
    existing = lab.region.get_job(doc_id)
    if existing and existing.get("state") == "running":
        return {"state": "running", "note": f"该文档已在索引中 (页 {existing.get('current_page')}/{existing.get('total_pages')})", "doc_id": doc_id}

    async def _run():
        try:
            await lab.region.index_document(doc_id)
        except Exception:
            logger.exception("background region index crashed for %s", doc_id)

    background_tasks.add_task(_run)
    lab.region._set_job(doc_id, state="pending", note="后台任务已排队")
    return {"state": "pending", "note": "后台索引已启动，请轮询 /api/lab/region/status/" + doc_id, "doc_id": doc_id}


@router.post("/region/index_all")
async def region_index_all(request: Request, background_tasks: BackgroundTasks, sync: bool = False):
    lab = _get_lab(request)
    if lab.region is None:
        raise HTTPException(status_code=503, detail="区域级检索服务未就绪")
    if sync:
        try:
            return await lab.region.index_all()
        except Exception as e:
            logger.exception("region index_all failed")
            raise HTTPException(status_code=500, detail=f"区域全量索引失败: {type(e).__name__}: {e}")

    async def _run_all():
        try:
            await lab.region.index_all()
        except Exception:
            logger.exception("background region index_all crashed")

    background_tasks.add_task(_run_all)
    return {"state": "pending", "note": "已在后台启动全部文档索引，请用 /api/lab/region/jobs 查看进度"}


@router.get("/region/status/{doc_id}")
async def region_status(request: Request, doc_id: str):
    lab = _get_lab(request)
    if lab.region is None:
        raise HTTPException(status_code=503, detail="区域级检索服务未就绪")
    job = lab.region.get_job(doc_id)
    if job is None:
        return {"doc_id": doc_id, "state": "not_started"}
    return job


@router.get("/region/jobs")
async def region_jobs(request: Request):
    lab = _get_lab(request)
    if lab.region is None:
        raise HTTPException(status_code=503, detail="区域级检索服务未就绪")
    return lab.region.list_jobs()


@router.delete("/region/{doc_id}")
async def region_delete(request: Request, doc_id: str):
    lab = _get_lab(request)
    if lab.region is None:
        raise HTTPException(status_code=503, detail="区域级检索服务未就绪")
    n = await lab.region.delete_document(doc_id)
    return {"deleted_doc": doc_id, "ok": n > 0}


# ---------------------------------------------------------------------------
# Phase 5 — Lab health
# ---------------------------------------------------------------------------

@router.get("/health", response_model=LabHealth)
async def lab_health(request: Request):
    lab = _get_lab(request)
    pipeline = getattr(request.app.state.pipeline_manager, "pipeline", None) \
        if getattr(request.app.state, "pipeline_manager", None) else None
    return await collect_lab_health(
        documents_db_path=lab.documents_db_path,
        bm25_doc_count=len(lab.hybrid._indexed_keys),
        region_service=lab.region,
        main_pipeline=pipeline,
    )


@router.get("/info")
async def lab_info():
    """Static info: which features are mounted and what they do."""
    return {
        "phases": [
            {"id": "hybrid",  "title": "双通道融合",   "endpoint": "/api/lab/hybrid",  "method": "POST",
             "desc": "BM25 文本通道 + ColPali 视觉通道 + RRF 融合，三路并排展示"},
            {"id": "visa",    "title": "证据归因",     "endpoint": "/api/lab/visa",    "method": "POST",
             "desc": "VISA 风格 bbox 高亮，把答案 [n] 标记落到具体版面元素"},
            {"id": "gmm",     "title": "动态深度",     "endpoint": "/api/lab/gmm",     "method": "POST",
             "desc": "高斯混合模型自适应 top-k，可视化分数分布与截断阈值"},
            {"id": "region",  "title": "区域级检索",   "endpoint": "/api/lab/region/query", "method": "POST",
             "desc": "Layout-level 检索：按文本块/表格/图表粒度返回命中"},
            {"id": "graph",   "title": "局部关系图",   "endpoint": "/api/lab/graph",   "method": "POST",
             "desc": "在候选页+邻接页内推导 caption / heading / 跨页续表 / 正文-图引用 等关系边"},
            {"id": "feedback","title": "反馈式补检索","endpoint": "/api/lab/feedback","method": "POST",
             "desc": "GMM 判定证据稳定度，必要时触发邻接页扩展或类型补检索，输出多轮轨迹"},
            {"id": "unified", "title": "统一编排",     "endpoint": "/api/lab/unified", "method": "POST",
             "desc": "一键串联 hybrid / gmm / feedback / visa / region / graph，逐阶段输出 ok 状态"},
            {"id": "benchmark","title": "基准评测",   "endpoint": "/api/lab/benchmark","method": "POST",
             "desc": "对一组带标注的 query 跑 MRR / Recall@K / Hit@1，比较 colpali / bm25 / rrf 通道"},
        ],
    }


# ---------------------------------------------------------------------------
# Phase 6 — Local relation graph
# ---------------------------------------------------------------------------

@router.post("/graph", response_model=GraphResponse)
async def graph_build(request: Request, body: GraphRequest):
    query = _validate_query(body.query)
    pipeline = _get_pipeline(request)
    lab = _get_lab(request)
    return await lab.graph.build_for_query(
        pipeline, query=query, top_k=body.top_k,
        include_neighbours=body.include_neighbours,
    )


# ---------------------------------------------------------------------------
# Phase 7 — Feedback-driven supplementary retrieval
# ---------------------------------------------------------------------------

@router.post("/feedback", response_model=FeedbackResponse)
async def feedback_loop(request: Request, body: FeedbackRequest):
    query = _validate_query(body.query)
    pipeline = _get_pipeline(request)
    return await feedback_retrieve(
        pipeline,
        query=query,
        top_k=body.top_k,
        candidates=body.candidates,
        max_rounds=body.max_rounds,
        do_generate=body.do_generate,
    )


# ---------------------------------------------------------------------------
# Phase 8 — Unified orchestration
# ---------------------------------------------------------------------------

@router.post("/unified", response_model=UnifiedResponse)
async def unified_run(request: Request, body: UnifiedRequest):
    query = _validate_query(body.query)
    pipeline = _get_pipeline(request)
    lab = _get_lab(request)
    if lab.unified is None:
        raise HTTPException(status_code=503, detail="统一编排服务未挂载")
    return await lab.unified.run(
        pipeline,
        query=query,
        top_k=body.top_k,
        candidates=body.candidates,
        use_hybrid=body.use_hybrid,
        use_gmm=body.use_gmm,
        use_feedback=body.use_feedback,
        use_visa=body.use_visa,
        use_region=body.use_region,
        use_graph=body.use_graph,
        do_generate=body.do_generate,
    )


# ---------------------------------------------------------------------------
# Phase 9 — Benchmark
# ---------------------------------------------------------------------------

@router.post("/benchmark", response_model=BenchmarkResponse)
async def benchmark_run(request: Request, body: BenchmarkRequest):
    if not body.queries:
        raise HTTPException(status_code=400, detail="queries 不能为空")
    if len(body.queries) > 200:
        raise HTTPException(status_code=400, detail="单次评测最多 200 个问题，请分批运行")
    pipeline = _get_pipeline(request)
    lab = _get_lab(request)
    try:
        return await run_benchmark(
            pipeline=pipeline,
            lab_bundle=lab,
            items=body.queries,
            channels=body.channels,
            top_k=body.top_k,
            timeout_per_query_sec=body.timeout_per_query_sec,
        )
    except Exception as e:
        logger.exception("benchmark crashed")
        raise HTTPException(status_code=500, detail=f"评测失败: {type(e).__name__}: {e}")
