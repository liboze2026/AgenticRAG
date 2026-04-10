from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    worker_client = request.app.state.worker_client
    qdrant_client = getattr(request.app.state, "qdrant_client", None)

    try:
        worker_status = await worker_client.health()
    except Exception as e:
        worker_status = {"status": "error", "detail": str(e)}

    qdrant_status = {"status": "unknown"}
    if qdrant_client is not None:
        try:
            await qdrant_client.get_collections()
            qdrant_status = {"status": "ok"}
        except Exception as e:
            qdrant_status = {"status": "error", "detail": str(e)}

    return {"status": "ok", "worker": worker_status, "qdrant": qdrant_status}
