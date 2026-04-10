"""Main entry point: load config, wire dependencies, start server."""
import os
import uvicorn

from backend.core.config import load_config
from backend.core.pipeline import PipelineManager
from backend.services.document_service import DocumentService
from backend.services.worker_client import WorkerClient
from backend.strategies import ALL_REGISTRIES, import_all_strategies
from backend.main import create_app


def main():
    config_path = os.environ.get("CONFIG_PATH", "config/default.yaml")
    config = load_config(config_path)

    # Import all strategies to trigger registration
    import_all_strategies()

    # Wire dependencies
    worker_client = WorkerClient(
        host=config.worker.host,
        port=config.worker.port,
        timeout=config.worker.timeout,
    )

    pipeline_manager = PipelineManager(ALL_REGISTRIES)
    pipeline_manager.set_pipeline(config.pipeline.model_dump())

    # Ensure storage dirs exist
    os.makedirs(config.storage.upload_dir, exist_ok=True)
    os.makedirs(config.storage.images_dir, exist_ok=True)

    document_service = DocumentService(
        upload_dir=config.storage.upload_dir,
        pipeline=pipeline_manager.pipeline,
    )

    app = create_app(
        worker_client=worker_client,
        pipeline_manager=pipeline_manager,
        document_service=document_service,
    )

    uvicorn.run(app, host=config.server.host, port=config.server.port)


if __name__ == "__main__":
    main()
