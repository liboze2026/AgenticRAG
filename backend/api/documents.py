import asyncio
from typing import Optional
from fastapi import APIRouter, Request, UploadFile, File, BackgroundTasks, HTTPException, Query

router = APIRouter()

# Cap concurrent indexing jobs — each one fans out hundreds of page encodes
# to the worker, so unbounded uploads (e.g. user drag-drops 10 PDFs at once)
# will OOM the GPU. Keep at most 2 in flight; further uploads queue.
_INDEX_SEMAPHORE = asyncio.Semaphore(2)


async def _bounded_index(doc_service, doc_id: str):
    async with _INDEX_SEMAPHORE:
        await doc_service.index_document(doc_id)


@router.post("/upload")
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    dataset_id: Optional[int] = Query(None),
):
    doc_service = request.app.state.document_service
    # Fix A: reject empty files
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")
    # Fix B: reject non-PDF files
    if not (file.filename or "").lower().endswith(".pdf") and file.content_type not in ("application/pdf",):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    doc_info = await doc_service.upload(filename=file.filename, content=content, dataset_id=dataset_id)
    background_tasks.add_task(_bounded_index, doc_service, doc_info.id)
    return doc_info.model_dump()


@router.get("")
async def list_documents(request: Request, dataset_id: Optional[int] = Query(None)):
    doc_service = request.app.state.document_service
    return [d.model_dump() for d in doc_service.list_documents(dataset_id=dataset_id)]


@router.get("/{doc_id}")
@router.get("/{doc_id}/status")
async def get_document_status(request: Request, doc_id: str):
    doc_service = request.app.state.document_service
    doc = doc_service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc.model_dump()


@router.delete("/{doc_id}")
async def delete_document(request: Request, doc_id: str):
    doc_service = request.app.state.document_service
    doc = doc_service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await doc_service.delete_document(doc_id)
    return {"status": "deleted"}


@router.post("/{doc_id}/retry")
async def retry_indexing(request: Request, doc_id: str, background_tasks: BackgroundTasks):
    doc_service = request.app.state.document_service
    doc = doc_service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status not in ("failed", "pending"):
        raise HTTPException(status_code=400, detail=f"Cannot retry document in status: {doc.status}")
    background_tasks.add_task(_bounded_index, doc_service, doc_id)
    return {"status": "queued"}
