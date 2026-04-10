from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/stats")
async def cache_stats(request: Request):
    qcache = getattr(request.app.state, "query_cache", None)
    gcache = getattr(request.app.state, "generation_cache", None)
    return {
        "query_cache": qcache.stats() if qcache else {"enabled": False, "entries": 0, "size_bytes": 0},
        "generation_cache": gcache.stats() if gcache else {"enabled": False, "entries": 0, "size_bytes": 0},
    }


@router.delete("/query")
async def clear_query_cache(request: Request):
    qcache = getattr(request.app.state, "query_cache", None)
    if qcache is None:
        return {"deleted": 0}
    return {"deleted": qcache.clear()}


@router.delete("/generation")
async def clear_generation_cache(request: Request):
    gcache = getattr(request.app.state, "generation_cache", None)
    if gcache is None:
        return {"deleted": 0}
    return {"deleted": gcache.clear()}
