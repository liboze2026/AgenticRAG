from typing import List
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class EncodeDocumentsRequest(BaseModel):
    image_paths: List[str]


class EncodeQueryRequest(BaseModel):
    query: str


@router.post("/documents")
async def encode_documents(request: Request, body: EncodeDocumentsRequest):
    manager = request.app.state.model_manager
    embeddings = manager.encode_images(body.image_paths)
    return {"embeddings": embeddings}


@router.post("/query")
async def encode_query(request: Request, body: EncodeQueryRequest):
    manager = request.app.state.model_manager
    vectors = manager.encode_query(body.query)
    return {"vectors": vectors}
