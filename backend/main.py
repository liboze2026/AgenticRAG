import os
import struct
import zlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from backend.api import documents, query, experiments, system, datasets, cache as cache_api
from backend.api import chat as chat_api


def _make_placeholder_png(width: int = 120, height: int = 90) -> bytes:
    """Generate a minimal gray placeholder PNG (no external deps)."""
    raw = b"".join(b"\x00" + bytes([220, 220, 220] * width) for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


_PLACEHOLDER_PNG = _make_placeholder_png()


def create_app(
    worker_client=None,
    pipeline_manager=None,
    document_service=None,
    experiment_service=None,
    dataset_service=None,
    chat_service=None,
    qdrant_client=None,
    cors_origins=None,
    query_cache=None,
    generation_cache=None,
) -> FastAPI:
    app = FastAPI(title="Multimodal Retrieval System")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.worker_client = worker_client
    app.state.pipeline_manager = pipeline_manager
    app.state.document_service = document_service
    app.state.experiment_service = experiment_service
    app.state.dataset_service = dataset_service
    app.state.chat_service = chat_service
    app.state.qdrant_client = qdrant_client
    app.state.query_cache = query_cache
    app.state.generation_cache = generation_cache

    app.include_router(system.router, prefix="/api")
    app.include_router(documents.router, prefix="/api/documents")
    app.include_router(query.router, prefix="/api")
    app.include_router(experiments.router, prefix="/api")
    app.include_router(datasets.router, prefix="/api/datasets")
    app.include_router(cache_api.router, prefix="/api/cache")
    app.include_router(chat_api.router, prefix="/api")

    # Serve page images — return placeholder PNG (200) when file missing
    images_dir = "data/images"
    os.makedirs(images_dir, exist_ok=True)

    @app.get("/api/images/{doc_id}/{filename}")
    async def serve_page_image(doc_id: str, filename: str):
        path = os.path.join(images_dir, doc_id, filename)
        if os.path.isfile(path):
            return FileResponse(path, media_type="image/png")
        return Response(content=_PLACEHOLDER_PNG, media_type="image/png")

    return app
