import asyncio
import uuid
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


@router.get("/{doc_id}/layout/{page_number}")
async def get_page_layout(request: Request, doc_id: str, page_number: int):
    """Return PageLayout (bbox + element list) for a single page.

    Reads back the layout payload that the indexer stored alongside the
    multi-vector point in Qdrant. Returns 404 when the page or its layout
    metadata is missing — the frontend treats 404 as "no layout available"
    and falls back to page-level rendering.
    """
    doc_service = request.app.state.document_service
    doc = doc_service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if page_number < 1 or page_number > doc.total_pages:
        raise HTTPException(status_code=404, detail="Page out of range")

    qdrant = getattr(request.app.state, "qdrant_client", None)
    if qdrant is None:
        raise HTTPException(status_code=503, detail="Qdrant client unavailable")

    # Same UUID5 derivation as MultiVectorRetriever.index
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}:{page_number}"))
    try:
        res = await qdrant.retrieve(
            collection_name="documents",
            ids=[point_id],
            with_payload=True,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Qdrant retrieve failed: {e}")

    if not res:
        raise HTTPException(status_code=404, detail="Page not indexed yet")
    payload = (res[0].payload or {})
    layout = payload.get("layout")
    if not layout:
        raise HTTPException(status_code=404, detail="No layout metadata for this page")
    return layout
