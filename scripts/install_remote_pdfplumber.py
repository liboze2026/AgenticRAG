"""Install pdfplumber into the active server's mrag_worker conda env."""
import os
import re
import sys
import paramiko
import yaml
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _resolve_env(value):
    if not isinstance(value, str): return value
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), value)


cfg = yaml.safe_load(open("config/default.yaml", encoding="utf-8"))
server = cfg["ssh_servers"][0]
pwd = _resolve_env(server.get("target_password", "")) or os.environ.get("SSH_PRIMARY_PASSWORD", "")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(server["target_host"], port=server["target_port"],
            username=server["target_user"], password=pwd, timeout=30)

cmd = (
    "source ~/miniconda3/etc/profile.d/conda.sh && "
    "conda activate mrag_worker && "
    "pip install pdfplumber 2>&1 | tail -10"
)
print(f"[run] {cmd}")
_, stdout, stderr = ssh.exec_command(cmd, timeout=300)
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err.strip():
    print("STDERR:", err[:1000])
ssh.close()
