"""Main entry point: load config, wire dependencies, start server."""
import asyncio
import atexit
import logging
import os
import re
import socket
import threading
import time
from typing import Optional

import paramiko
import uvicorn
from qdrant_client import AsyncQdrantClient

from backend.core.config import load_config, AppConfig
from backend.core.pipeline import PipelineManager
from backend.services.cache import DiskCache
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


def _resolve_env(value: str) -> str:
    """Resolve ${VAR} references in a string."""
    if not isinstance(value, str):
        return value
    pattern = re.compile(r"\$\{(\w+)\}")
    def replacer(m):
        return os.environ.get(m.group(1), m.group(0))
    return pattern.sub(replacer, value)


def _forward_tunnel(local_port: int, remote_port: int, transport: paramiko.Transport):
    """Accept local connections and forward them through the SSH transport."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", local_port))
    server.listen(5)
    server.settimeout(1.0)
    logger.info("Forwarding 127.0.0.1:%d -> remote:localhost:%d", local_port, remote_port)

    def handle_client(client_sock):
        try:
            chan = transport.open_channel(
                "direct-tcpip", ("localhost", remote_port),
                client_sock.getpeername(),
            )
        except Exception as e:
            logger.error("Forward channel open failed: %s", e)
            client_sock.close()
            return
        while True:
            import select
            r, _, _ = select.select([client_sock, chan], [], [], 1.0)
            if client_sock in r:
                data = client_sock.recv(32768)
                if not data:
                    break
                chan.sendall(data)
            if chan in r:
                data = chan.recv(32768)
                if not data:
                    break
                client_sock.sendall(data)
        chan.close()
        client_sock.close()

    def accept_loop():
        while True:
            try:
                client_sock, addr = server.accept()
                t = threading.Thread(target=handle_client, args=(client_sock,), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except OSError:
                break

    t = threading.Thread(target=accept_loop, daemon=True)
    t.start()
    return server


def _start_ssh_tunnel(config: AppConfig):
    """Start SSH tunnel via paramiko (supports password auth to target)."""
    raw = _read_raw_yaml(os.environ.get("CONFIG_PATH", "config/default.yaml"))
    ssh = raw.get("ssh_tunnel") or {}
    if not ssh.get("enabled"):
        return None

    bastion_host = ssh.get("bastion_host", "")
    bastion_port = ssh.get("bastion_port", 22)
    bastion_user = ssh.get("bastion_user", "")
    bastion_key = os.path.expanduser(ssh.get("bastion_key", ""))
    target_host = ssh.get("target_host", "")
    target_port = ssh.get("target_port", 22)
    target_user = ssh.get("target_user", "")
    target_password = _resolve_env(ssh.get("target_password", ""))
    forwards = ssh.get("forwards", [])

    if not (bastion_host and target_host and forwards):
        logger.warning("SSH tunnel enabled but config is incomplete; skipping")
        return None

    # Connect to bastion
    logger.info("Connecting to bastion %s@%s:%d", bastion_user, bastion_host, bastion_port)
    bastion = paramiko.SSHClient()
    bastion.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    bastion.connect(bastion_host, port=bastion_port, username=bastion_user,
                    key_filename=bastion_key if os.path.exists(bastion_key) else None)

    # Open channel to target through bastion
    bastion_transport = bastion.get_transport()
    channel = bastion_transport.open_channel(
        "direct-tcpip", (target_host, target_port), ("127.0.0.1", 0)
    )

    # Connect to target via channel
    logger.info("Connecting to target %s@%s:%d via bastion", target_user, target_host, target_port)
    target = paramiko.SSHClient()
    target.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    target.connect(target_host, port=target_port, username=target_user,
                   password=target_password, sock=channel)

    target_transport = target.get_transport()
    servers = []
    for fwd in forwards:
        srv = _forward_tunnel(fwd["local"], fwd["remote"], target_transport)
        servers.append(srv)

    def cleanup():
        for srv in servers:
            try:
                srv.close()
            except Exception:
                pass
        target.close()
        bastion.close()

    atexit.register(cleanup)
    logger.info("SSH tunnel established with %d port forwards", len(forwards))
    return (bastion, target, servers)


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
        time.sleep(1)  # give tunnel threads time to bind
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

    # Build caches
    query_cache = DiskCache(path=config.cache.query_cache_dir, enabled=config.cache.enabled)
    generation_cache = DiskCache(path=config.cache.generation_cache_dir, enabled=config.cache.enabled)

    # Build deps for strategy DI
    deps = {
        "worker_client": worker_client,
        "qdrant_client": qdrant_client,
        "collection_name": config.qdrant.collection_name,
        "images_dir": config.storage.images_dir,
        "openai_api_key": config.api_keys.openai,
        "anthropic_api_key": config.api_keys.anthropic,
        "query_cache": query_cache,
        "generation_cache": generation_cache,
    }

    pipeline_manager = PipelineManager(ALL_REGISTRIES, deps=deps)
    pipeline_manager.set_pipeline(config.pipeline.model_dump() if hasattr(config.pipeline, "model_dump") else config.pipeline.dict())

    document_service = DocumentService(
        upload_dir=config.storage.upload_dir,
        pipeline=pipeline_manager.pipeline,
    )

    # Recover orphaned indexing tasks from previous crash
    recovered = document_service.recover_orphaned()
    if recovered:
        logger.warning("Marked %d orphaned documents as failed: %s", len(recovered), recovered)

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
        query_cache=query_cache,
        generation_cache=generation_cache,
    )

    uvicorn.run(app, host=config.server.host, port=config.server.port)


if __name__ == "__main__":
    main()
