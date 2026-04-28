"""Run a command on the remote GPU server via bastion. Usage: rrun.py "<cmd>"."""
import os
import sys
import io
from dotenv import load_dotenv
import paramiko

# Force UTF-8 stdout/stderr on Windows so emoji + unicode in remote output don't blow up
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT, ".env"))

KEY = os.path.expanduser(os.environ.get("SSH_BASTION_KEY", ""))
PASSWORD = os.environ.get("SSH_TARGET_PASSWORD", "")
BASTION = "vlab.ustc.edu.cn"
TARGET_HOST = "202.38.68.70"
TARGET_PORT = 2266
TARGET_USER = "bzli"

cmd = sys.argv[1] if len(sys.argv) > 1 else "echo 'no cmd'"

bastion = paramiko.SSHClient()
bastion.set_missing_host_key_policy(paramiko.AutoAddPolicy())
bastion.connect(BASTION, port=22, username="ubuntu", key_filename=KEY,
                look_for_keys=False, allow_agent=False, timeout=15)

chan = bastion.get_transport().open_channel(
    "direct-tcpip", (TARGET_HOST, TARGET_PORT), ("127.0.0.1", 0)
)
target = paramiko.SSHClient()
target.set_missing_host_key_policy(paramiko.AutoAddPolicy())
target.connect(TARGET_HOST, port=TARGET_PORT, username=TARGET_USER,
               password=PASSWORD, sock=chan, timeout=25,
               look_for_keys=False, allow_agent=False)

stdin_, stdout, stderr = target.exec_command(cmd, timeout=300)
out = stdout.read().decode(errors="replace")
err = stderr.read().decode(errors="replace")
sys.stdout.write(out)
if err.strip():
    sys.stderr.write("\n--- stderr ---\n" + err)
sys.exit(stdout.channel.recv_exit_status())
