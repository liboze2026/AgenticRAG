"""
Push visdom_remote.py to remote, run it via worker conda env, pull results back.
"""
import os, sys, io, time
from dotenv import load_dotenv
import paramiko

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT, ".env"))

KEY = os.path.expanduser(os.environ["SSH_BASTION_KEY"])
PASSWORD = os.environ["SSH_TARGET_PASSWORD"]

bastion = paramiko.SSHClient()
bastion.set_missing_host_key_policy(paramiko.AutoAddPolicy())
bastion.connect("vlab.ustc.edu.cn", port=22, username="ubuntu",
                key_filename=KEY, look_for_keys=False, allow_agent=False, timeout=15)

chan = bastion.get_transport().open_channel(
    "direct-tcpip", ("202.38.68.70", 2266), ("127.0.0.1", 0)
)
target = paramiko.SSHClient()
target.set_missing_host_key_policy(paramiko.AutoAddPolicy())
target.connect("202.38.68.70", port=2266, username="bzli",
               password=PASSWORD, sock=chan, timeout=25,
               look_for_keys=False, allow_agent=False)
print("[+] connected")

REMOTE_SCRIPT = "/tmp/visdom_remote.py"
sftp = target.open_sftp()
sftp.put(os.path.join(PROJECT, "scripts", "visdom_remote.py"), REMOTE_SCRIPT)
print(f"[+] pushed {REMOTE_SCRIPT}")
sftp.close()

cmd = (
    "source ~/miniconda3/etc/profile.d/conda.sh && "
    "conda activate mrag_worker && "
    "pip install -q pdf2image requests 2>/dev/null; "
    f"python {REMOTE_SCRIPT}"
)
print(f"[+] running: {cmd}\n")

stdin_, stdout, stderr = target.exec_command(cmd, timeout=3600, get_pty=True)
# Stream output line-by-line
for line in iter(stdout.readline, ""):
    sys.stdout.write(line)
    sys.stdout.flush()
err = stderr.read().decode(errors="replace")
if err.strip():
    sys.stderr.write("\n--- stderr ---\n" + err)
exit_code = stdout.channel.recv_exit_status()
print(f"\n[+] remote exit code: {exit_code}")
if exit_code != 0:
    target.close()
    bastion.close()
    sys.exit(exit_code)

# Pull results.json
print("\n[+] pulling results.json")
sftp = target.open_sftp()
local_dir = os.path.join(PROJECT, "frontend", "public", "visdom")
os.makedirs(local_dir, exist_ok=True)
sftp.get("/tmp/visdom_out/results.json", os.path.join(local_dir, "results.json"))
print(f"  saved: {os.path.join(local_dir, 'results.json')}")

# Pull all page screenshots referenced in results
print("[+] pulling page screenshots ...")
import json
with open(os.path.join(local_dir, "results.json"), encoding="utf-8") as f:
    res = json.load(f)
papers = res["manifest"]["papers"]
pages_local_dir = os.path.join(local_dir, "pages")
os.makedirs(pages_local_dir, exist_ok=True)
for arxiv in papers:
    paper_dir = os.path.join(pages_local_dir, arxiv)
    os.makedirs(paper_dir, exist_ok=True)
    remote_paper_dir = f"/tmp/visdom_out/pages/{arxiv}"
    try:
        files = sftp.listdir(remote_paper_dir)
    except IOError:
        print(f"  [{arxiv}] no pages dir on remote")
        continue
    for fname in files:
        local_path = os.path.join(paper_dir, fname)
        if not os.path.exists(local_path):
            sftp.get(f"{remote_paper_dir}/{fname}", local_path)
    print(f"  [{arxiv}] {len(files)} pages")
sftp.close()

# Also dump a copy outside frontend (for git ignore)
backup = os.path.join(PROJECT, "data", "visdom_spiqa_mini")
os.makedirs(backup, exist_ok=True)
import shutil
shutil.copy(os.path.join(local_dir, "results.json"), os.path.join(backup, "results.json"))
print(f"[+] backup: {os.path.join(backup, 'results.json')}")

target.close()
bastion.close()
print("[+] DONE")
