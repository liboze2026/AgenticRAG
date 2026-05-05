try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
"""Install sentence-transformers on remote mrag_worker conda env."""
import os, re, paramiko, yaml

def _r(v):
    if not isinstance(v, str): return v
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), v)

cfg = yaml.safe_load(open("config/default.yaml", encoding="utf-8"))
s = cfg["ssh_servers"][0]
pwd = _r(s.get("target_password", "")) or os.environ.get("SSH_PRIMARY_PASSWORD", "")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(s["target_host"], port=s["target_port"], username=s["target_user"], password=pwd, timeout=30)

cmd = (
    "source ~/miniconda3/etc/profile.d/conda.sh && "
    "conda activate mrag_worker && "
    "pip install -q sentence-transformers 2>&1 | tail -10"
)
print(f"[run] {cmd}")
_, stdout, stderr = ssh.exec_command(cmd, timeout=900)
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err.strip(): print("STDERR:", err[:500])
ssh.close()
