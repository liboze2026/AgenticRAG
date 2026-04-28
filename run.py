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
from backend.services.chat_service import ChatService
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


def _ssh_connect(ssh_cfg: dict):
    """Return (bastion, target) paramiko clients connected via jump host."""
    bastion_host = ssh_cfg.get("bastion_host", "")
    bastion_port = ssh_cfg.get("bastion_port", 22)
    bastion_user = ssh_cfg.get("bastion_user", "")
    bastion_key  = os.path.expanduser(_resolve_env(ssh_cfg.get("bastion_key", "")))
    target_host  = ssh_cfg.get("target_host", "")
    target_port  = ssh_cfg.get("target_port", 22)
    target_user  = ssh_cfg.get("target_user", "")
    target_password = _resolve_env(ssh_cfg.get("target_password", ""))

    bastion = paramiko.SSHClient()
    bastion.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    bastion.connect(bastion_host, port=bastion_port, username=bastion_user,
                    key_filename=bastion_key if os.path.exists(bastion_key) else None)

    channel = bastion.get_transport().open_channel(
        "direct-tcpip", (target_host, target_port), ("127.0.0.1", 0)
    )
    target = paramiko.SSHClient()
    target.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    target.connect(target_host, port=target_port, username=target_user,
                   password=target_password, sock=channel)
    return bastion, target


def _wait_for_remote_port(client: paramiko.SSHClient, port: int, timeout: float = 15.0) -> bool:
    """Poll a remote port via SSH until it's listening or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        out, _ = _remote_run(client,
            f"ss -tlnp 2>/dev/null | grep ':{port}' | head -1", show=False)
        if out.strip():
            return True
        time.sleep(1.0)
    return False


def _remote_run(client: paramiko.SSHClient, cmd: str, show: bool = True) -> tuple:
    _, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if show and out.strip():
        logger.info("[remote] %s", out.strip()[:300])
    if show and err.strip():
        logger.info("[remote stderr] %s", err.strip()[:300])
    return out, err


def _start_remote_services(ssh: dict, deploy: dict):
    """Start Qdrant and Worker on remote GPU server via SSH."""
    if not ssh.get("enabled"):
        return

    remote_base   = deploy.get("remote_base", "/home/bzli/mrag_app")
    conda_env     = deploy.get("conda_env", "mrag_worker")
    qdrant_path   = deploy.get("qdrant_path", "~/qdrant")
    qdrant_storage = deploy.get("qdrant_storage", "~/qdrant/storage")
    gpu_devices   = deploy.get("gpu_devices", "0")

    logger.info("=== Starting remote services (Qdrant + Worker) ===")
    try:
        bastion, target = _ssh_connect(ssh)

        # --- 1. Start Qdrant (skip if already running) ---
        logger.info("Starting Qdrant on remote server...")
        if not _wait_for_remote_port(target, 6333, timeout=3):
            _remote_run(target,
                f"mkdir -p {qdrant_storage} && "
                f"cd {qdrant_path} && "
                f"nohup env QDRANT__STORAGE__STORAGE_PATH={qdrant_storage} "
                f"./qdrant > {qdrant_path}/qdrant.log 2>&1 &",
                show=False)
            if _wait_for_remote_port(target, 6333, timeout=15):
                logger.info("Qdrant is up on port 6333.")
            else:
                logger.info("Qdrant starting (may still be initializing).")
        else:
            logger.info("Qdrant already running on port 6333, skipping restart.")

        # --- 2. Upload worker code ---
        logger.info("Uploading worker code...")
        sftp = target.open_sftp()

        def _sftp_mkdir_p(path: str):
            parts = [p for p in path.split("/") if p]
            current = ""
            for part in parts:
                current += "/" + part
                try:
                    sftp.stat(current)
                except FileNotFoundError:
                    try:
                        sftp.mkdir(current)
                    except OSError:
                        pass  # race condition: another process created it concurrently

        project_root = os.path.dirname(os.path.abspath(__file__))
        local_worker = os.path.join(project_root, "worker")

        for root, _, files in os.walk(local_worker):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                local_path  = os.path.join(root, fname)
                rel         = os.path.relpath(local_path, project_root).replace("\\", "/")
                remote_path = remote_base + "/" + rel
                _sftp_mkdir_p(os.path.dirname(remote_path))
                sftp.put(local_path, remote_path)
                logger.info("  uploaded: %s", rel)

        sftp.close()
        logger.info("Worker code upload complete.")

        # --- 3. Start Worker (skip if already running) ---
        logger.info("Checking Worker on remote server (GPU %s)...", gpu_devices)
        if not _wait_for_remote_port(target, 8001, timeout=3):
            _remote_run(target, "pkill -f 'uvicorn worker.main:app' 2>/dev/null || true", show=False)
            start_cmd = (
                f"cd {remote_base} && "
                "source ~/miniconda3/etc/profile.d/conda.sh && "
                f"conda activate {conda_env} && "
                f"WORKER_STANDALONE=1 CUDA_VISIBLE_DEVICES={gpu_devices} "
                "HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "
                "nohup python -m uvicorn worker.main:app "
                f"--host 0.0.0.0 --port 8001 > {remote_base}/worker.log 2>&1 &"
            )
            _remote_run(target, start_cmd, show=False)
            logger.info("Worker process launched (model loading takes ~2 min).")
        else:
            logger.info("Worker already running on port 8001, skipping restart.")

        target.close()
        bastion.close()
        logger.info("=== Remote services launched ===")

    except (paramiko.AuthenticationException, paramiko.SSHException, OSError) as e:
        logger.warning("Could not start remote services: %s — continuing without them.", e)


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

        def sock_to_chan():
            try:
                while True:
                    data = client_sock.recv(1048576)
                    if not data:
                        break
                    chan.sendall(data)
            except Exception:
                pass
            finally:
                try: chan.shutdown(True)
                except Exception: pass

        def chan_to_sock():
            try:
                while True:
                    data = chan.recv(1048576)
                    if not data:
                        break
                    client_sock.sendall(data)
            except Exception:
                pass
            finally:
                try: client_sock.close()
                except Exception: pass

        t1 = threading.Thread(target=sock_to_chan, daemon=True)
        t2 = threading.Thread(target=chan_to_sock, daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        try: chan.close()
        except Exception: pass
        try: client_sock.close()
        except Exception: pass

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


def _start_ssh_tunnel(ssh: dict):
    """Start SSH tunnel via paramiko (supports password auth to target)."""
    if not ssh.get("enabled"):
        return None

    forwards = ssh.get("forwards", [])
    if not (ssh.get("bastion_host") and ssh.get("target_host") and forwards):
        logger.warning("SSH tunnel enabled but config is incomplete; skipping")
        return None

    logger.info("Establishing SSH tunnel...")
    bastion, target = _ssh_connect(ssh)

    target_transport = target.get_transport()
    servers = []
    for fwd in forwards:
        srv = _forward_tunnel(fwd["local"], fwd["remote"], target_transport)
        servers.append(srv)

    def cleanup():
        for srv in servers:
            try:
                srv.close()
            except OSError:
                pass
        target.close()
        bastion.close()

    atexit.register(cleanup)
    logger.info("SSH tunnel established with %d port forwards", len(servers))
    return (bastion, target, servers)


async def _ensure_qdrant_collection(qdrant_client, collection_name: str, vector_size: int = 128):
    """Create Qdrant collection if missing."""
    from qdrant_client import models
    from qdrant_client.http.exceptions import UnexpectedResponse
    try:
        await qdrant_client.get_collection(collection_name)
        logger.info("Qdrant collection '%s' exists", collection_name)
    except UnexpectedResponse:
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
    # Load .env file if present (before reading config so ${VAR} refs resolve)
    try:
        from dotenv import load_dotenv
        load_dotenv(override=False)
    except ImportError:
        pass

    # Bypass Windows system proxy for loopback addresses (Qdrant/Worker on localhost)
    for _var in ("NO_PROXY", "no_proxy"):
        existing = os.environ.get(_var, "")
        bypass = "localhost,127.0.0.1,127.*,::1"
        os.environ[_var] = f"{existing},{bypass}" if existing else bypass

    config_path = os.environ.get("CONFIG_PATH", "config/default.yaml")
    raw = _read_raw_yaml(config_path)
    config = load_config(config_path)
    ssh = raw.get("ssh_tunnel") or {}
    deploy = raw.get("ssh_deployment") or {}

    # Step 1: Start remote services (Qdrant + Worker) via SSH
    _start_remote_services(ssh, deploy)

    # Step 2: Set up SSH port-forward tunnel (8001, 6333 -> local)
    tunnel = None
    try:
        tunnel = _start_ssh_tunnel(ssh)
    except (paramiko.AuthenticationException, paramiko.SSHException, OSError) as e:
        logger.warning("SSH tunnel failed: %s — backend will start without remote services.", e)

    if tunnel:
        # Wait for tunnel socket to bind before polling the forwarded port
        _wait_for_port("127.0.0.1", config.worker.port, timeout=2)
        logger.info("Waiting for worker port %d (model loading may take ~2 min)...", config.worker.port)
        if not _wait_for_port(config.worker.host, config.worker.port, timeout=180):
            logger.warning("Worker port %d not reachable after 3 min; continuing anyway", config.worker.port)
        else:
            logger.info("Worker is ready.")

    # Import strategies
    import_all_strategies()

    # Build clients
    worker_client = WorkerClient(
        host=config.worker.host,
        port=config.worker.port,
        timeout=config.worker.timeout,
    )
    qdrant_client = AsyncQdrantClient(host=config.qdrant.host, port=config.qdrant.port, timeout=300)

    # Ensure storage dirs
    os.makedirs(config.storage.upload_dir, exist_ok=True)
    os.makedirs(config.storage.images_dir, exist_ok=True)

    # Ensure Qdrant collection
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            _ensure_qdrant_collection(qdrant_client, config.qdrant.collection_name)
        )
        loop.close()
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
        "zhipu_api_key": config.api_keys.zhipu,
        "query_cache": query_cache,
        "generation_cache": generation_cache,
    }

    pipeline_manager = PipelineManager(ALL_REGISTRIES, deps=deps)
    pipeline_manager.set_pipeline(config.pipeline.model_dump() if hasattr(config.pipeline, "model_dump") else config.pipeline.dict())

    document_service = DocumentService(
        upload_dir=config.storage.upload_dir,
        pipeline=pipeline_manager.pipeline,
    )

    recovered = document_service.recover_orphaned()
    if recovered:
        logger.warning("Marked %d orphaned documents as failed: %s", len(recovered), recovered)

    experiment_service = ExperimentService(
        db_path=os.path.join(config.storage.upload_dir, "experiments.db"),
    )

    dataset_service = DatasetService(
        db_path=os.path.join(config.storage.upload_dir, "datasets.db"),
    )

    chat_service = ChatService(
        db_path=os.path.join(config.storage.upload_dir, "chat.db"),
    )

    app = create_app(
        worker_client=worker_client,
        pipeline_manager=pipeline_manager,
        document_service=document_service,
        experiment_service=experiment_service,
        dataset_service=dataset_service,
        chat_service=chat_service,
        qdrant_client=qdrant_client,
        cors_origins=config.server.cors_origins,
        query_cache=query_cache,
        generation_cache=generation_cache,
    )

    port = config.server.port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", port)) == 0:
            logger.error(
                "Port %d is already in use by another process. "
                "Kill that process first (e.g. netstat -ano | findstr :%d) "
                "or change server.port in config/default.yaml.",
                port, port,
            )
            raise SystemExit(1)
    uvicorn.run(app, host=config.server.host, port=port)


if __name__ == "__main__":
    main()
