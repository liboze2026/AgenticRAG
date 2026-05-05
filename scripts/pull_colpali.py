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
ssh.connect(s["target_host"], port=s["target_port"], username=s["target_user"], password=pwd, timeout=30)
remote = f"{s['deployment']['visdom_data']}/sota_colpali"
local = "data/sota_runs/colpali"
os.makedirs(local, exist_ok=True)
sftp = ssh.open_sftp()
for f in sftp.listdir(remote):
    rp = f"{remote}/{f}"; lp = os.path.join(local, f)
    sftp.get(rp, lp)
    print(f"[pull] {f} ({os.path.getsize(lp)} B)")
sftp.close(); ssh.close()
