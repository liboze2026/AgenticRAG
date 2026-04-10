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
