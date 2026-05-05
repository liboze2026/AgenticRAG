import os, re, paramiko, yaml
def _r(v):
    if not isinstance(v, str): return v
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), v)
cfg = yaml.safe_load(open("config/default.yaml", encoding="utf-8"))
s = cfg["ssh_servers"][0]
pwd = _r(s.get("target_password", "")) or os.environ.get("SSH_PRIMARY_PASSWORD", "")
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(s["target_host"], port=s["target_port"], username=s["target_user"], password=pwd, timeout=30)
root = s["deployment"]["visdom_data"]
for sub in ["feta_tab", "paper_tab", "scigraphvqa", "slidevqa", "spiqa"]:
    _, out, _ = ssh.exec_command(f"ls {root}/{sub}/docs | wc -l; du -sh {root}/{sub}/docs")
    print(f"{sub}:", out.read().decode().strip().replace("\n", " | "))
ssh.close()
