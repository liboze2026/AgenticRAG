import base64
import io
from typing import List, Optional
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class EncodeDocumentsRequest(BaseModel):
    images_b64: Optional[List[str]] = None  # base64-encoded PNG/JPEG
    image_paths: Optional[List[str]] = None  # legacy: local paths (only works if worker is local)


class EncodeQueryRequest(BaseModel):
    query: str


@router.post("/documents")
async def encode_documents(request: Request, body: EncodeDocumentsRequest):
    from PIL import Image
    manager = request.app.state.model_manager
    if body.images_b64 is not None:
        images = [Image.open(io.BytesIO(base64.b64decode(b))).convert("RGB") for b in body.images_b64]
        embeddings = manager.encode_images_pil(images)
    else:
        embeddings = manager.encode_images(body.image_paths or [])
    return {"embeddings": embeddings}


@router.post("/query")
async def encode_query(request: Request, body: EncodeQueryRequest):
    manager = request.app.state.model_manager
    vectors = manager.encode_query(body.query)
    return {"vectors": vectors}
