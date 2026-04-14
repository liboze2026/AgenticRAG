"""Deploy worker code + start Qdrant + download VisDoM on remote GPU server."""
import os
import time
import paramiko


def get_connection():
    bastion = paramiko.SSHClient()
    bastion.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    bastion.connect(
        os.environ['SSH_BASTION_HOST'],
        port=int(os.environ.get('SSH_BASTION_PORT', '22')),
        username=os.environ['SSH_BASTION_USER'],
        key_filename=os.environ['SSH_BASTION_KEY'],
    )
    transport = bastion.get_transport()
    target_host = os.environ['SSH_TARGET_HOST']
    target_port = int(os.environ.get('SSH_TARGET_PORT', '22'))
    channel = transport.open_channel('direct-tcpip', (target_host, target_port), ('127.0.0.1', 0))
    gpu = paramiko.SSHClient()
    gpu.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    gpu.connect(target_host, port=target_port, username=os.environ['SSH_TARGET_USER'],
                password=os.environ['SSH_TARGET_PASSWORD'], sock=channel)
    return bastion, gpu


def run_cmd(gpu, cmd, show=True):
    stdin, stdout, stderr = gpu.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if show:
        if out.strip():
            print(out)
        if err.strip():
            print("STDERR:", err[-300:])
    return out, err


def main():
    bastion, gpu = get_connection()

    # 1. Start Qdrant
    print("=" * 50)
    print("=== Starting Qdrant ===")
    # Kill any existing qdrant first
    run_cmd(gpu, "pkill -f './qdrant' 2>/dev/null; sleep 1", show=False)
    run_cmd(gpu, "cd ~/qdrant && nohup ./qdrant --storage-path ~/qdrant/storage > ~/qdrant/qdrant.log 2>&1 &")
    time.sleep(3)
    out, _ = run_cmd(gpu, "ss -tlnp 2>/dev/null | grep 6333 || echo 'port 6333 NOT open'")
    out2, _ = run_cmd(gpu, "tail -5 ~/qdrant/qdrant.log")

    # 2. Upload worker code via SFTP
    print("=" * 50)
    print("=== Uploading worker code ===")
    sftp = gpu.open_sftp()

    worker_base = r"C:\bzli\paper\agent"
    remote_base = "/home/bzli/mrag_app"

    # Create remote directories
    for d in [remote_base, remote_base + "/worker", remote_base + "/worker/endpoints"]:
        try:
            sftp.mkdir(d)
        except IOError:
            pass

    # Upload all .py files in worker/
    local_worker = os.path.join(worker_base, "worker")
    for root, dirs, files in os.walk(local_worker):
        for f in files:
            if f.endswith(".py"):
                local_path = os.path.join(root, f)
                rel = os.path.relpath(local_path, worker_base).replace("\\", "/")
                remote_path = remote_base + "/" + rel
                remote_dir = os.path.dirname(remote_path)
                try:
                    sftp.stat(remote_dir)
                except FileNotFoundError:
                    sftp.mkdir(remote_dir)
                sftp.put(local_path, remote_path)
                print(f"  Uploaded: {rel}")

    sftp.close()

    # Verify
    out, _ = run_cmd(gpu, f"find {remote_base} -name '*.py' | sort")

    # 3. Start worker on GPU 0
    print("=" * 50)
    print("=== Starting Worker on GPU 0 ===")
    run_cmd(gpu, "pkill -f 'uvicorn worker.main:app' 2>/dev/null; sleep 1", show=False)

    start_cmd = (
        f"cd {remote_base} && "
        "source ~/miniconda3/etc/profile.d/conda.sh && "
        "conda activate mrag_worker && "
        "CUDA_VISIBLE_DEVICES=0 nohup python -m uvicorn worker.main:app "
        "--host 0.0.0.0 --port 8001 > ~/mrag_app/worker.log 2>&1 &"
    )
    run_cmd(gpu, start_cmd)
    time.sleep(5)

    out, _ = run_cmd(gpu, "ss -tlnp 2>/dev/null | grep 8001 || echo 'port 8001 NOT open'")
    out2, _ = run_cmd(gpu, "tail -20 ~/mrag_app/worker.log")

    # 4. Download VisDoM dataset
    print("=" * 50)
    print("=== Downloading VisDoM dataset ===")
    visdom_cmd = (
        "mkdir -p ~/mrag_app/datasets && cd ~/mrag_app/datasets && "
        "if [ -d VisDoM ]; then echo 'VisDoM already exists'; else "
        "git clone https://github.com/MananSuri27/VisDoM.git 2>&1; fi"
    )
    out, err = run_cmd(gpu, visdom_cmd)

    print("=" * 50)
    print("=== Checking VisDoM ===")
    run_cmd(gpu, "ls -la ~/mrag_app/datasets/VisDoM/ 2>/dev/null | head -20")

    # Final status check
    print("=" * 50)
    print("=== Final Status ===")
    run_cmd(gpu, "ss -tlnp 2>/dev/null | grep -E '6333|8001'")
    run_cmd(gpu, "nvidia-smi | grep -A2 'GPU  Name' | head -5")

    gpu.close()
    bastion.close()
    print("\n=== ALL DEPLOYMENT COMPLETE ===")


if __name__ == "__main__":
    main()
