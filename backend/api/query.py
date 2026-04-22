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


@router.post("/query")
async def query(request: Request, body: QueryRequest):
    # Fix C: reject empty query string
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    pipeline = request.app.state.pipeline_manager.pipeline
    try:
        answer = await pipeline.query(body.query, top_k=body.top_k)
    except (httpx.HTTPStatusError, httpx.ConnectError, Exception) as exc:
        raise _service_error(exc)
    return {
        "answer": answer.text,
        "sources": [s.model_dump() for s in answer.sources],
        "timing": answer.timing,
    }


@router.post("/retrieve")
async def retrieve(request: Request, body: QueryRequest):
    # Fix C: reject empty query string
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    pipeline = request.app.state.pipeline_manager.pipeline
    try:
        bundle = await pipeline.retrieve(body.query, top_k=body.top_k)
    except (httpx.HTTPStatusError, httpx.ConnectError, Exception) as exc:
        raise _service_error(exc)
    return {
        "results": [r.model_dump() for r in bundle.results],
        "timing": bundle.timing,
    }
