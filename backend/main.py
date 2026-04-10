import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api import documents, query, experiments, system


def create_app(worker_client=None, pipeline_manager=None, document_service=None, experiment_service=None, qdrant_client=None, cors_origins=None) -> FastAPI:
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
    app.state.qdrant_client = qdrant_client
    app.include_router(system.router, prefix="/api")
    app.include_router(documents.router, prefix="/api/documents")
    app.include_router(query.router, prefix="/api")
    app.include_router(experiments.router, prefix="/api")

    # Serve page images for frontend evidence panel
    images_dir = "data/images"
    if os.path.isdir(images_dir):
        app.mount("/api/images", StaticFiles(directory=images_dir), name="images")

    return app
