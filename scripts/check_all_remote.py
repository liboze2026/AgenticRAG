try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
import os, re, paramiko, yaml
def _r(v):
    if not isinstance(v, str): return v
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), v)
cfg = yaml.safe_load(open("config/default.yaml", encoding="utf-8"))
s = cfg["ssh_servers"][0]
pwd = _r(s.get("target_password", "")) or os.environ.get("SSH_PRIMARY_PASSWORD", "")
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(s["target_host"], port=s["target_port"], username=s["target_user"], password=pwd, timeout=20)
root = s["deployment"]["visdom_data"]
cmd = (
    f"echo '=== sota_text ==='; ls -la {root}/sota_text 2>&1 | tail -8\n"
    f"echo '=== sota_text_ocr ==='; ls -la {root}/sota_text_ocr 2>&1 | tail -8\n"
    f"echo '=== sota_dense ==='; ls -la {root}/sota_dense 2>&1 | tail -8\n"
    f"echo '=== procs ==='; ps -ef | grep -E 'extract_visdom' | grep -v grep | head -20\n"
    f"echo '=== gpu ==='; nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv 2>&1 | head -5\n"
)
_, stdout, _ = ssh.exec_command(cmd)
print(stdout.read().decode("utf-8", errors="replace"))
ssh.close()
