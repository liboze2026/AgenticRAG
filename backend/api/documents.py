from fastapi import APIRouter, Request, UploadFile, File, BackgroundTasks, HTTPException

router = APIRouter()


@router.post("/upload")
async def upload_document(request: Request, background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    doc_service = request.app.state.document_service
    content = await file.read()
    doc_info = await doc_service.upload(filename=file.filename, content=content)
    background_tasks.add_task(doc_service.index_document, doc_info.id)
    return doc_info.model_dump()


@router.get("")
async def list_documents(request: Request):
    doc_service = request.app.state.document_service
    return [d.model_dump() for d in doc_service.list_documents()]


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
