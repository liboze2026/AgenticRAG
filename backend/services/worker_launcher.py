"""Single source of truth for how we spawn the remote ColPali worker.

Why this module exists
----------------------
Previously the launch command was written twice — once in
`run.py:_start_remote_services` and once in `worker_watchdog`. The two
versions were not equivalent:

* run.py: ``nohup python -m uvicorn ... > worker.log 2>&1 &``
* watchdog: ``setsid nohup <script> </dev/null >/dev/null 2>&1 & disown``

The first one only catches SIGHUP. It leaves the worker in the SSH
session's process group with stdin still attached to the SSH channel
master. autodl's sshd cleans that group asynchronously after the
paramiko client closes, so the worker dies seconds-to-minutes later
with no traceback in worker.log and no entry in dmesg — the exact
"silent worker death" we have been firefighting all afternoon.

The watchdog version is correct: ``setsid`` puts the worker in its own
session (orphaned to PID 1), and stdin is redirected to /dev/null so
no SSH-channel close can propagate any signal.

This module is the only place that knows the launch incantation. Both
run.py and the watchdog import :func:`launch_worker`.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import paramiko

logger = logging.getLogger(__name__)


def launch_worker(
    client: paramiko.SSHClient,
    deploy_cfg: Dict[str, Any],
    *,
    kill_existing: bool = False,
) -> Optional[str]:
    """Launch the worker fully-detached on the remote host.

    Args:
        client: an open paramiko.SSHClient connection to the GPU box.
            Caller owns the connection lifecycle (we do not close it).
        deploy_cfg: the server's ``deployment`` block from
            ``config/default.yaml``. Reads ``remote_base``, ``conda_env``,
            ``gpu_devices``, ``hf_home``.
        kill_existing: if True, pkill any existing worker first. The
            watchdog passes True (force replace a stale/zombie listener);
            run.py leaves it False so a healthy running worker isn't
            disturbed.

    Returns:
        The worker PID as reported by ``echo $!``, or None if the read
        timed out / the channel was closed before the pid arrived. The
        worker still launches either way — pid is purely diagnostic.

    Side effects:
        Writes ``<remote_base>/start_worker.sh`` (idempotent) and starts
        the worker in a new session detached from this SSH connection.
    """
    remote_base = deploy_cfg.get("remote_base", "")
    conda_env = deploy_cfg.get("conda_env", "mrag_worker")
    gpu = deploy_cfg.get("gpu_devices", "0")
    hf_home = deploy_cfg.get("hf_home", "")

    if not remote_base:
        raise ValueError("worker_launcher: deploy_cfg.remote_base is required")

    if kill_existing:
        _, out, _ = client.exec_command(
            "pkill -9 -f 'uvicorn worker.main:app' 2>/dev/null || true",
            timeout=10,
        )
        try: out.read()
        except Exception: pass

    # Write a launcher script (idempotent) so the actual start invocation
    # is one short paramiko channel exec.
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
    sftp = client.open_sftp()
    launch_path = f"{remote_base}/start_worker.sh"
    with sftp.open(launch_path, "w") as f:
        f.write(launcher)
    sftp.chmod(launch_path, 0o755)
    sftp.close()

    # Fire the launcher in a fully detached session. The three crucial
    # bits, none of which are negotiable:
    #   setsid     — new session, new process group, no controlling tty
    #   </dev/null — stdin disconnected from the SSH channel master
    #   >/dev/null 2>&1 — stdout/stderr disconnected from the SSH channel
    # 'disown' is belt-and-suspenders against shell-level pgrp cleanup.
    transport = client.get_transport()
    chan = transport.open_session()
    chan.exec_command(
        f"setsid nohup {launch_path} </dev/null >/dev/null 2>&1 & echo $!; disown"
    )
    chan.settimeout(3)
    pid: Optional[str] = None
    try:
        out = chan.recv(200).decode(errors="replace").strip()
        if out and out.isdigit():
            pid = out
    except Exception:
        pass
    chan.close()
    logger.info("worker launcher: spawned worker (pid=%s)", pid or "?")
    return pid
