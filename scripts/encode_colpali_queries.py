"""Batch-encode VisDoMBench slidevqa test queries via remote ColPali.

Runs the colpali query encoder on remote (cached model, GPU) for all
test-split queries; returns each query's multi-vector embedding as a
list of float32 arrays. Saves locally to data/sota_runs/colpali/
slidevqa_queries.npz + .keys.jsonl.

closed_set_colpali then loads these pre-encoded vectors instead of
calling the worker per query (no tunnel needed).
"""
try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError: pass
import argparse
import json
import os
import re
import sys
import paramiko
import yaml


REMOTE_SCRIPT = r'''#!/usr/bin/env python
import json, os, sys
import numpy as np
import torch
try:
    from colpali_engine.models import ColPali, ColPaliProcessor
except ImportError as e:
    print(f"missing: {{e}}", file=sys.stderr); sys.exit(2)

QUERIES_PATH = "{queries_path}"
OUT_DIR = "{out_dir}"
os.makedirs(OUT_DIR, exist_ok=True)

# Load ColPali from worker cache
from pathlib import Path
hf_home = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
snap_root = Path(hf_home) / "hub" / "models--vidore--colpali-v1.2" / "snapshots"
snaps = list(snap_root.iterdir())
model_path = str(snaps[0]) if snaps else "vidore/colpali-v1.2"
print(f"[load] {{model_path}}")
model = ColPali.from_pretrained(model_path, device_map="auto").eval()
processor = ColPaliProcessor.from_pretrained(model_path)
device = next(model.parameters()).device
print(f"[loaded] device={{device}}")

queries = []
with open(QUERIES_PATH, "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            queries.append(json.loads(line))
print(f"[encode] {{len(queries)}} queries")

embs = []
keys = []
for i, q in enumerate(queries):
    try:
        inputs = processor.process_queries([q["query"][:500]])
        inputs = {{k: v.to(device) for k, v in inputs.items()}}
        with torch.no_grad():
            emb = model(**inputs)
        v = emb[0].cpu().numpy().astype("float16")  # (n_q_patches, dim)
        embs.append(v)
        keys.append({{"query_id": q["query_id"], "n_patches": int(v.shape[0])}})
        if (i + 1) % 50 == 0: print(f"  {{i+1}}/{{len(queries)}}")
    except Exception as e:
        print(f"[err] q {{q['query_id']}}: {{e}}")
        embs.append(np.zeros((1, 128), dtype="float16"))
        keys.append({{"query_id": q["query_id"], "n_patches": 1}})

# Pad to max
max_p = max(e.shape[0] for e in embs)
dim = embs[0].shape[1]
stacked = np.zeros((len(embs), max_p, dim), dtype="float16")
for i, e in enumerate(embs):
    stacked[i, :e.shape[0]] = e

np.savez_compressed(os.path.join(OUT_DIR, "slidevqa_queries.npz"), embs=stacked)
with open(os.path.join(OUT_DIR, "slidevqa_queries.keys.jsonl"), "w", encoding="utf-8") as f:
    for k in keys:
        f.write(json.dumps(k, ensure_ascii=False) + "\n")
print(f"[done] saved")
'''


def _r(v):
    if not isinstance(v, str): return v
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="if set, only encode the first N queries (for smoke)")
    ap.add_argument("--split", default="test", choices=["test", "train"],
                    help="which split to encode")
    ap.add_argument("--out_suffix", default="",
                    help="suffix for output files (e.g. _train)")
    args = ap.parse_args()

    cfg = yaml.safe_load(open("config/default.yaml", encoding="utf-8"))
    s = cfg["ssh_servers"][0]
    pwd = _r(s.get("target_password", "")) or os.environ.get("SSH_PRIMARY_PASSWORD", "")
    visdom_root = s["deployment"]["visdom_data"]

    # Stage local test queries to remote
    local_q = "data/sota_runs/datasets/slidevqa/queries.jsonl"
    if not os.path.exists(local_q):
        print(f"missing {local_q}"); sys.exit(1)

    # Filter by split (deterministic SHA1) + optional limit
    import hashlib
    def split(qid):
        h = int(hashlib.sha1(qid.encode("utf-8")).hexdigest()[:4], 16)
        return "train" if h < 32768 else "test"
    target_split = getattr(args, "split", "test")
    rows_kept = []
    with open(local_q, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if split(str(row.get("query_id", ""))) == target_split:
                rows_kept.append(row)
                if args.limit and len(rows_kept) >= args.limit:
                    break
    test_rows = rows_kept
    print(f"staging {len(test_rows)} {target_split}-split queries → remote")

    remote_queries = f"/tmp/slidevqa_{args.split}_queries.jsonl"
    remote_out = f"{visdom_root}/sota_colpali_q{args.out_suffix}"
    remote_script = "/tmp/encode_colpali_queries.py"

    payload = REMOTE_SCRIPT.format(queries_path=remote_queries, out_dir=remote_out)
    ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(s["target_host"], port=s["target_port"], username=s["target_user"], password=pwd, timeout=30)
    sftp = ssh.open_sftp()
    with sftp.file(remote_queries, "w") as f:
        for r in test_rows:
            f.write(json.dumps({"query_id": str(r["query_id"]), "query": r["query"]}, ensure_ascii=False) + "\n")
    with sftp.file(remote_script, "w") as f:
        f.write(payload)
    sftp.close()

    cmd = (
        "source ~/miniconda3/etc/profile.d/conda.sh && "
        "conda activate mrag_worker && "
        "HF_HOME=/root/autodl-tmp/liboze/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "
        f"python -u {remote_script}"
    )
    chan = ssh.get_transport().open_session()
    chan.set_combine_stderr(True)
    chan.exec_command(cmd)
    while True:
        if chan.recv_ready():
            d = chan.recv(4096).decode("utf-8", errors="replace")
            sys.stdout.write(d); sys.stdout.flush()
        if chan.exit_status_ready():
            while chan.recv_ready():
                d = chan.recv(4096).decode("utf-8", errors="replace")
                sys.stdout.write(d); sys.stdout.flush()
            break
    print(f"[exit] {chan.recv_exit_status()}")

    # Pull
    sftp = ssh.open_sftp()
    out_local = "data/sota_runs/colpali"
    os.makedirs(out_local, exist_ok=True)
    suffix = args.out_suffix
    for f in sftp.listdir(remote_out):
        rp = f"{remote_out}/{f}"
        # Append suffix before file extension to avoid overwriting test cache
        if suffix and f.startswith("slidevqa_queries"):
            base, ext = (f.split(".", 1)[0], "." + f.split(".", 1)[1]) if "." in f else (f, "")
            local_name = base + suffix + ext
        else:
            local_name = f
        lp = os.path.join(out_local, local_name)
        sftp.get(rp, lp)
        print(f"[pull] {f} → {local_name} ({os.path.getsize(lp)} B)")
    sftp.close(); ssh.close()


if __name__ == "__main__":
    main()
