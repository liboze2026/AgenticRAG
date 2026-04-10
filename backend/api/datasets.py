from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter()


class CreateDataset(BaseModel):
    name: str
    description: str = ""


@router.post("")
async def create_dataset(request: Request, body: CreateDataset):
    svc = request.app.state.dataset_service
    try:
        ds = svc.create(body.name, body.description)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ds.model_dump()


@router.get("")
async def list_datasets(request: Request):
    svc = request.app.state.dataset_service
    doc_svc = request.app.state.document_service
    counts = doc_svc.count_by_dataset() if doc_svc else {}
    return [d.model_dump() for d in svc.list_all(document_counts=counts)]


@router.delete("/{ds_id}")
async def delete_dataset(request: Request, ds_id: int):
    svc = request.app.state.dataset_service
    ok = svc.delete(ds_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"status": "deleted"}
