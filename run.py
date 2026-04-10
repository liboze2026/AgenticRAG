"""Main entry point: load config, wire dependencies, start server."""
import asyncio
import atexit
import logging
import os
import socket
import subprocess
import time
from typing import Optional

import uvicorn
from qdrant_client import AsyncQdrantClient

from backend.core.config import load_config, AppConfig
from backend.core.pipeline import PipelineManager
from backend.services.dataset_service import DatasetService
from backend.services.document_service import DocumentService
from backend.services.experiment_service import ExperimentService
from backend.services.worker_client import WorkerClient
from backend.strategies import ALL_REGISTRIES, import_all_strategies
from backend.main import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _wait_for_port(host: str, port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _read_raw_yaml(path: str) -> dict:
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _start_ssh_tunnel(config: AppConfig) -> Optional[subprocess.Popen]:
    """Start SSH tunnel as subprocess if enabled in config."""
    raw = _read_raw_yaml(os.environ.get("CONFIG_PATH", "config/default.yaml"))
    ssh = raw.get("ssh_tunnel") or {}
    if not ssh.get("enabled"):
        return None

    pem = os.path.expanduser(ssh.get("pem_path", ""))
    bastion = ssh.get("bastion", "")
    target = ssh.get("target", "")
    forwards = ssh.get("forwards", [])

    if not (pem and bastion and target and forwards):
        logger.warning("SSH tunnel enabled but config is incomplete; skipping")
        return None
    if not os.path.exists(pem):
        logger.warning("SSH pem file not found at %s; skipping tunnel", pem)
        return None

    cmd = ["ssh", "-i", pem, "-J", bastion, target, "-N",
           "-o", "ServerAliveInterval=60", "-o", "ServerAliveCountMax=3",
           "-o", "StrictHostKeyChecking=no"]
    for fwd in forwards:
        cmd += ["-L", f"{fwd['local']}:localhost:{fwd['remote']}"]

    logger.info("Starting SSH tunnel: %s -> %s", bastion, target)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    atexit.register(lambda: proc.terminate() if proc.poll() is None else None)
    return proc


async def _ensure_qdrant_collection(qdrant_client, collection_name: str, vector_size: int = 128):
    """Create Qdrant collection if missing."""
    from qdrant_client import models
    try:
        await qdrant_client.get_collection(collection_name)
        logger.info("Qdrant collection '%s' exists", collection_name)
    except Exception:
        logger.info("Creating Qdrant collection '%s'", collection_name)
        await qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
                multivector_config=models.MultiVectorConfig(
                    comparator=models.MultiVectorComparator.MAX_SIM,
                ),
            ),
        )


def main():
    config_path = os.environ.get("CONFIG_PATH", "config/default.yaml")
    config = load_config(config_path)

    # Optionally start SSH tunnel
    tunnel = _start_ssh_tunnel(config)
    if tunnel:
        logger.info("Waiting for worker port %d...", config.worker.port)
        if not _wait_for_port(config.worker.host, config.worker.port, timeout=30):
            logger.warning("Worker port %d not reachable; continuing anyway", config.worker.port)

    # Import strategies
    import_all_strategies()

    # Build clients
    worker_client = WorkerClient(
        host=config.worker.host,
        port=config.worker.port,
        timeout=config.worker.timeout,
    )
    qdrant_client = AsyncQdrantClient(host=config.qdrant.host, port=config.qdrant.port)

    # Ensure storage dirs
    os.makedirs(config.storage.upload_dir, exist_ok=True)
    os.makedirs(config.storage.images_dir, exist_ok=True)

    # Ensure Qdrant collection
    try:
        asyncio.get_event_loop().run_until_complete(
            _ensure_qdrant_collection(qdrant_client, config.qdrant.collection_name)
        )
    except Exception as e:
        logger.warning("Could not ensure Qdrant collection: %s", e)

    # Build deps for strategy DI
    deps = {
        "worker_client": worker_client,
        "qdrant_client": qdrant_client,
        "collection_name": config.qdrant.collection_name,
        "images_dir": config.storage.images_dir,
        "openai_api_key": config.api_keys.openai,
        "anthropic_api_key": config.api_keys.anthropic,
    }

    pipeline_manager = PipelineManager(ALL_REGISTRIES, deps=deps)
    pipeline_manager.set_pipeline(config.pipeline.model_dump() if hasattr(config.pipeline, "model_dump") else config.pipeline.dict())

    document_service = DocumentService(
        upload_dir=config.storage.upload_dir,
        pipeline=pipeline_manager.pipeline,
    )

    experiment_service = ExperimentService(
        db_path=os.path.join(config.storage.upload_dir, "experiments.db"),
    )

    dataset_service = DatasetService(
        db_path=os.path.join(config.storage.upload_dir, "datasets.db"),
    )

    app = create_app(
        worker_client=worker_client,
        pipeline_manager=pipeline_manager,
        document_service=document_service,
        experiment_service=experiment_service,
        dataset_service=dataset_service,
        qdrant_client=qdrant_client,
        cors_origins=config.server.cors_origins,
    )

    uvicorn.run(app, host=config.server.host, port=config.server.port)


if __name__ == "__main__":
    main()
