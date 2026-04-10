from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/query")
async def query(request: Request, body: QueryRequest):
    pipeline = request.app.state.pipeline_manager.pipeline
    answer = await pipeline.query(body.query, top_k=body.top_k)
    return {
        "answer": answer.text,
        "sources": [s.model_dump() for s in answer.sources],
        "timing": answer.timing,
    }


@router.post("/retrieve")
async def retrieve(request: Request, body: QueryRequest):
    pipeline = request.app.state.pipeline_manager.pipeline
    bundle = await pipeline.retrieve(body.query, top_k=body.top_k)
    return {
        "results": [r.model_dump() for r in bundle.results],
        "timing": bundle.timing,
    }
