"""Pull whatever sota_text/*.jsonl files are currently complete on remote.
Skips .tmp files (in-progress)."""
import os, re, paramiko, yaml

def _r(v):
    if not isinstance(v, str): return v
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), v)

cfg = yaml.safe_load(open("config/default.yaml", encoding="utf-8"))
s = cfg["ssh_servers"][0]
pwd = _r(s.get("target_password", "")) or os.environ.get("SSH_PRIMARY_PASSWORD", "")
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(s["target_host"], port=s["target_port"], username=s["target_user"], password=pwd, timeout=30)

remote = f"{s['deployment']['visdom_data']}/sota_text"
local = "data/sota_runs/corpus"
os.makedirs(local, exist_ok=True)

sftp = ssh.open_sftp()
files = sftp.listdir(remote)
for f in files:
    if not f.endswith(".jsonl"):
        continue
    rp = f"{remote}/{f}"
    lp = os.path.join(local, f)
    rsize = sftp.stat(rp).st_size
    lsize = os.path.getsize(lp) if os.path.exists(lp) else 0
    if rsize == lsize and lsize > 0:
        print(f"[skip] {f} (already up to date, {lsize} B)")
        continue
    sftp.get(rp, lp)
    print(f"[pull] {f} ({rsize} B)")
sftp.close(); ssh.close()
