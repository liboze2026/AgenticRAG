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
from backend.services.worker_launcher import launch_worker

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

        if not (host and user and pwd and self._deploy_cfg.get("remote_base")):
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
            pid = launch_worker(c, self._deploy_cfg, kill_existing=True)
            logger.warning("worker watchdog: relaunched remote worker (pid=%s)", pid or "?")
        except Exception:
            logger.exception("worker watchdog: launch_worker failed")
        finally:
            try: c.close()
            except Exception: pass
