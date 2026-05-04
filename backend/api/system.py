import asyncio

from fastapi import APIRouter, Request

from backend.services.qdrant_resilient import ResilientAsyncQdrantClient

router = APIRouter()


# /health gates the whole frontend (it polls every 8s) and feeds /api/lab/health.
# When the SSH tunnel is busy with heavy traffic (e.g. region indexing),
# Qdrant's get_collections() can stall for ~30s while ResilientAsyncQdrantClient
# retries — and a cascade of 30s health stalls makes the whole UI feel dead.
# Cap each subsystem probe at HEALTH_PROBE_TIMEOUT_SEC and fall back to
# {status: "degraded"} when it expires. A real 5xx from worker/qdrant still
# surfaces with status="error".
HEALTH_PROBE_TIMEOUT_SEC = 4.0


@router.get("/health")
async def health(request: Request):
    worker_client = request.app.state.worker_client
    qdrant_client = getattr(request.app.state, "qdrant_client", None)

    async def _probe_worker():
        try:
            return await worker_client.health()
        except Exception as e:
            return {"status": "error", "detail": str(e)[:200]}

    async def _probe_qdrant():
        if qdrant_client is None:
            return {"status": "unknown"}
        # Bypass the resilient retry wrapper for /health — we want a single
        # short-timeout probe. _inner.get_collections is the raw qdrant client
        # method so a network blip surfaces immediately.
        inner = qdrant_client._inner if isinstance(qdrant_client, ResilientAsyncQdrantClient) else qdrant_client
        try:
            await inner.get_collections()
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "detail": str(e)[:200]}

    async def _bounded(coro):
        try:
            return await asyncio.wait_for(coro, timeout=HEALTH_PROBE_TIMEOUT_SEC)
        except asyncio.TimeoutError:
            return {"status": "degraded", "detail": "probe timeout (>4s)"}

    # Run worker + qdrant probes concurrently — total wall-clock time stays
    # ~4s in the worst case rather than 8s.
    worker_status, qdrant_status = await asyncio.gather(
        _bounded(_probe_worker()),
        _bounded(_probe_qdrant()),
    )

    return {"status": "ok", "worker": worker_status, "qdrant": qdrant_status}
