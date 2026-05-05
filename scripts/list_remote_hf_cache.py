try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError: pass
import os, re, paramiko, yaml
def _r(v):
    if not isinstance(v, str): return v
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), v)
cfg = yaml.safe_load(open("config/default.yaml", encoding="utf-8"))
s = cfg["ssh_servers"][0]
pwd = _r(s.get("target_password", "")) or os.environ.get("SSH_PRIMARY_PASSWORD", "")
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(s["target_host"], port=s["target_port"], username=s["target_user"], password=pwd, timeout=20)
hf = s["deployment"].get("hf_home", "")
cmd = (
    f"ls -la {hf} 2>&1; echo ---; ls -la {hf}/hub 2>&1 | head -30; echo ---; "
    f"find {hf} -maxdepth 5 -name 'config.json' 2>/dev/null | head -20"
)
_, stdout, _ = ssh.exec_command(cmd, timeout=60)
print(stdout.read().decode("utf-8", errors="replace"))
ssh.close()
