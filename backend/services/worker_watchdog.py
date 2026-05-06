"""Worker watchdog — re-launches the remote worker when it dies.

Background: the autodl GPU instances we run on appear to silently kill
nohup'd worker processes after some idle period (no OOM trace, no
signal logged in worker.log — just gone). Symptoms: `/api/health` shows
`worker.status=error` while SSH transport stays alive, so the existing
SSH keepalive monitor doesn't trigger any recovery. Every lab endpoint
that needs the query encoder times out.

This watchdog adds a second loop on top of WorkerClient.health():
* every CHECK_INTERVAL_SEC, call worker.health()
* on 2 consecutive failures (≈60s of unreachability), SSH in and
  relaunch the worker via a detached `setsid nohup` launcher script
* sleep WARMUP_AFTER_RESTART_SEC after a successful restart so we don't
  count the model-load window as another outage
* expose state (last failure, last recovery, recoveries count) so it
  can be surfaced in /api/health for visibility

The launcher script lives at `<remote_base>/start_worker.sh`. Once
written it is reused on subsequent restarts.

Operations on the SSH side use a single short-lived paramiko client
per restart attempt — we do NOT share state with the SSH keepalive
monitor (it has its own concerns and locking it would couple two
unrelated paths).
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
import time
from typing import Any, Dict, Optional

import paramiko

from backend.services.worker_client import WorkerClient

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SEC = 30.0           # how often we probe worker.health()
FAILURE_TRIGGER = 2                 # consecutive failures before restart
WARMUP_AFTER_RESTART_SEC = 90.0     # silence checks after a restart while model loads
RESTART_COOLDOWN_SEC = 180.0        # min spacing between consecutive restart attempts
SSH_TIMEOUT_SEC = 20.0


def _resolve_env(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), value)


class WorkerWatchdog:
    """Polls the worker and re-launches it on the remote host when it dies."""

    def __init__(
        self,
        worker_client: WorkerClient,
        ssh_cfg: Dict[str, Any],
        deploy_cfg: Dict[str, Any],
    ):
        self._worker = worker_client
        self._ssh_cfg = ssh_cfg
        self._deploy_cfg = deploy_cfg or {}
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()
        # Diagnostic state — read by /api/health.
        self._consecutive_failures = 0
        self._last_check_at: Optional[float] = None
        self._last_check_ok: Optional[bool] = None
        self._last_failure_reason: Optional[str] = None
        self._last_restart_at: Optional[float] = None
        self._restart_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._task is not None:
            return
        if not self._ssh_cfg or not self._deploy_cfg:
            logger.warning("worker watchdog: missing ssh_cfg/deploy_cfg — disabled")
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="worker-watchdog")
        logger.info(
            "worker watchdog started (interval=%.0fs, trigger=%d failures)",
            CHECK_INTERVAL_SEC, FAILURE_TRIGGER,
        )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop.set()
        try:
            await asyncio.wait_for(self._task, timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
        self._task = None

    def status(self) -> Dict[str, Any]:
        return {
            "consecutive_failures": self._consecutive_failures,
            "last_check_at": self._last_check_at,
            "last_check_ok": self._last_check_ok,
            "last_failure_reason": self._last_failure_reason,
            "last_restart_at": self._last_restart_at,
            "restart_count": self._restart_count,
        }

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        # Initial grace — first prewarm + model load already happened during
        # backend startup, so don't immediately mistake a slow first check
        # for a failure.
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=CHECK_INTERVAL_SEC)
            return
        except asyncio.TimeoutError:
            pass

        while not self._stop.is_set():
            try:
                await self._check_once()
            except Exception:
                logger.exception("worker watchdog: unexpected error in check loop")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=CHECK_INTERVAL_SEC)
                return
            except asyncio.TimeoutError:
                continue

    async def _check_once(self) -> None:
        self._last_check_at = time.time()
        try:
            await self._worker.health()
            ok = True
            reason = None
        except Exception as e:
            ok = False
            reason = f"{type(e).__name__}: {e}"
        self._last_check_ok = ok

        if ok:
            if self._consecutive_failures > 0:
                logger.info("worker watchdog: worker recovered (was %d consecutive failures)",
                            self._consecutive_failures)
            self._consecutive_failures = 0
            self._last_failure_reason = None
            return

        self._consecutive_failures += 1
        self._last_failure_reason = reason
        logger.warning("worker watchdog: health check failed (%d consecutive): %s",
                       self._consecutive_failures, reason)
        if self._consecutive_failures < FAILURE_TRIGGER:
            return

        # Throttle restart attempts.
        now = time.time()
        if self._last_restart_at is not None and now - self._last_restart_at < RESTART_COOLDOWN_SEC:
            wait = RESTART_COOLDOWN_SEC - (now - self._last_restart_at)
            logger.info("worker watchdog: cooldown active (%.0fs left), skipping restart", wait)
            return

        async with self._lock:
            await self._restart_remote_worker()
            self._last_restart_at = time.time()
            self._restart_count += 1
            self._consecutive_failures = 0
            logger.info("worker watchdog: restart issued — sleeping %.0fs for model warmup",
                        WARMUP_AFTER_RESTART_SEC)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=WARMUP_AFTER_RESTART_SEC)
            except asyncio.TimeoutError:
                pass

    async def _restart_remote_worker(self) -> None:
        """SSH in, write/refresh the launcher script, fire it detached.

        Runs the blocking paramiko work in a thread so the asyncio loop
        keeps serving requests while we restart the worker.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._restart_remote_worker_blocking)

    def _restart_remote_worker_blocking(self) -> None:
        host = self._ssh_cfg.get("target_host")
        port = self._ssh_cfg.get("target_port", 22)
        user = self._ssh_cfg.get("target_user")
        pwd = _resolve_env(self._ssh_cfg.get("target_password", ""))

        remote_base = self._deploy_cfg.get("remote_base", "")
        conda_env = self._deploy_cfg.get("conda_env", "mrag_worker")
        gpu = self._deploy_cfg.get("gpu_devices", "0")
        hf_home = self._deploy_cfg.get("hf_home", "")

        if not (host and user and pwd and remote_base):
            logger.error("worker watchdog: incomplete SSH config — cannot restart")
            return

        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            c.connect(host, port=port, username=user, password=pwd,
                      timeout=SSH_TIMEOUT_SEC, look_for_keys=False, allow_agent=False)
        except Exception as e:
            logger.error("worker watchdog: SSH connect failed: %s", e)
            return

        try:
            # Kill any zombie listener on 8001 so the new launch can bind.
            self._exec(c, "pkill -9 -f 'uvicorn worker.main:app' 2>/dev/null || true", timeout=10)

            # Write the launcher script (idempotent).
            hf_env = f"HF_HOME={hf_home} " if hf_home else ""
            launcher = (
                "#!/bin/bash\n"
                f"cd {remote_base}\n"
                "source ~/miniconda3/etc/profile.d/conda.sh\n"
                f"conda activate {conda_env}\n"
                f"export WORKER_STANDALONE=1 CUDA_VISIBLE_DEVICES={gpu} "
                f"{hf_env}HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1\n"
                "exec python -m uvicorn worker.main:app --host 0.0.0.0 --port 8001 "
                f">> {remote_base}/worker.log 2>&1\n"
            )
            sftp = c.open_sftp()
            launch_path = f"{remote_base}/start_worker.sh"
            with sftp.open(launch_path, "w") as f:
                f.write(launcher)
            sftp.chmod(launch_path, 0o755)
            sftp.close()

            # Fire the launcher in a detached session so closing this SSH
            # connection does not propagate SIGHUP to the worker process.
            transport = c.get_transport()
            chan = transport.open_session()
            chan.exec_command(
                f"setsid nohup {launch_path} </dev/null >/dev/null 2>&1 & echo $!; disown"
            )
            chan.settimeout(3)
            try:
                pid_out = chan.recv(200).decode(errors="replace").strip()
            except Exception:
                pid_out = ""
            chan.close()
            logger.warning("worker watchdog: relaunched remote worker (pid=%s)", pid_out or "?")
        finally:
            try: c.close()
            except Exception: pass

    @staticmethod
    def _exec(client: paramiko.SSHClient, cmd: str, timeout: float = 30.0) -> str:
        _, out, _ = client.exec_command(cmd, timeout=timeout)
        try:
            return out.read().decode(errors="replace")
        except Exception:
            return ""
