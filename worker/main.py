from fastapi import FastAPI
from worker.endpoints import encode


def create_worker_app(model_manager=None) -> FastAPI:
    app = FastAPI(title="Multimodal Retrieval Worker")
    app.state.model_manager = model_manager
    app.include_router(encode.router, prefix="/encode")

    @app.get("/health")
    async def health():
        return {"status": "ok", "model": app.state.model_manager.model_name()}

    return app


import os as _os

if _os.environ.get("WORKER_STANDALONE", "0") == "1":
    def _build_default_app() -> FastAPI:
        """Build app with real model for production deployment via uvicorn."""
        from worker.model_manager import ModelManager
        import logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        logger.info("Loading ColPali model...")
        mm = ModelManager()
        mm.load()
        logger.info("Model loaded successfully")
        return create_worker_app(model_manager=mm)

    app = _build_default_app()
