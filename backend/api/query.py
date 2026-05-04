import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


def _service_error(exc: Exception) -> HTTPException:
    msg = str(exc)
    if "502" in msg or "503" in msg or "Connection refused" in msg:
        return HTTPException(status_code=503, detail="Remote worker/Qdrant not available. Check SSH tunnel.")
    return HTTPException(status_code=500, detail=msg)


def _get_pipeline(request: Request):
    pm = getattr(request.app.state, "pipeline_manager", None)
    if pm is None or pm.pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="主 pipeline 未就绪 — 请检查 worker / Qdrant 是否在线",
        )
    return pm.pipeline


@router.post("/query")
async def query(request: Request, body: QueryRequest):
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if len(body.query) > 4000:
        raise HTTPException(status_code=400, detail="Query too long (>4000 chars)")
    pipeline = _get_pipeline(request)
    try:
        answer = await pipeline.query(body.query, top_k=body.top_k)
    except HTTPException:
        raise
    except Exception as exc:
        raise _service_error(exc)
    return {
        "answer": answer.text,
        "sources": [s.model_dump() for s in answer.sources],
        "timing": answer.timing,
    }


@router.post("/retrieve")
async def retrieve(request: Request, body: QueryRequest):
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if len(body.query) > 4000:
        raise HTTPException(status_code=400, detail="Query too long (>4000 chars)")
    pipeline = _get_pipeline(request)
    try:
        bundle = await pipeline.retrieve(body.query, top_k=body.top_k)
    except HTTPException:
        raise
    except Exception as exc:
        raise _service_error(exc)
    return {
        "results": [r.model_dump() for r in bundle.results],
        "timing": bundle.timing,
    }
