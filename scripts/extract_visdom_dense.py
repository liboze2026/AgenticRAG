"""Pre-compute per-doc dense text embeddings on remote worker GPU.

Reads $VISDOM_REMOTE/sota_text/<subset>.jsonl (page-level text), encodes
each page with sentence-transformers `BAAI/bge-base-en-v1.5` on CUDA, dumps
dense vectors to $VISDOM_REMOTE/sota_dense/<subset>.npz with parallel
$VISDOM_REMOTE/sota_dense/<subset>.keys.jsonl listing (doc_id, page_number)
in matching order.

After remote run, SFTP-pulls both files to data/sota_runs/dense/<subset>.*

Reasoning for choosing bge-base-en-v1.5:
* Strong zero-shot text retrieval performance on MTEB
* 768-dim → small footprint (~2-3 GB total for ~1000 docs × ~5 pages each)
* Cheap inference: ~1k pages/sec on a 4090
* Same family as bge-large/m3 for easy upgrade path

Run locally:
    SSH_PRIMARY_PASSWORD=<pwd> python scripts/extract_visdom_dense.py
"""
import argparse
import os
import re
import sys

import paramiko
import yaml


REMOTE_SCRIPT = r'''#!/usr/bin/env python
"""Worker-side dense encoder. Reads sota_text/*.jsonl, writes sota_dense/*.npz + .keys.jsonl."""
import json
import os
import sys

try:
    import numpy as np
    import torch
    from sentence_transformers import SentenceTransformer
except ImportError as e:
    print(f"missing dep on worker: {{e}}", file=sys.stderr)
    sys.exit(2)

ROOT = "{visdom_root}"
TXT  = os.path.join(ROOT, "sota_text")
OUT  = os.path.join(ROOT, "sota_dense")
os.makedirs(OUT, exist_ok=True)

MODEL_NAME = "BAAI/bge-base-en-v1.5"
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[load] model={{MODEL_NAME}} device={{device}}")
model = SentenceTransformer(MODEL_NAME, device=device)

SUBSETS = ["feta_tab", "paper_tab", "scigraphvqa", "slidevqa", "spiqa"]

for subset in SUBSETS:
    src = os.path.join(TXT, subset + ".jsonl")
    if not os.path.exists(src):
        print(f"[skip] {{subset}}: no text file at {{src}}")
        continue
    out_npz = os.path.join(OUT, subset + ".npz")
    out_keys = os.path.join(OUT, subset + ".keys.jsonl")
    if os.path.exists(out_npz) and os.path.getsize(out_npz) > 0:
        print(f"[skip] {{subset}}: dense already exists")
        continue

    keys = []
    texts = []
    with open(src, "r", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except Exception:
                continue
            t = (row.get("text") or "").strip()
            if not t:
                continue
            keys.append({{"doc_id": row.get("doc_id"), "page_number": int(row.get("page_number") or 0)}})
            texts.append(t[:8000])  # cap context window
    if not texts:
        print(f"[empty] {{subset}}")
        continue

    print(f"[encode] {{subset}}: {{len(texts)}} pages")
    batch_size = 32
    embs = model.encode(texts, batch_size=batch_size, show_progress_bar=False,
                        convert_to_numpy=True, normalize_embeddings=True)

    np.savez_compressed(out_npz, embs=embs.astype("float32"))
    with open(out_keys, "w", encoding="utf-8") as f:
        for k in keys:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")
    print(f"[ok] {{subset}}: {{embs.shape}} → {{out_npz}}, {{out_keys}}")

print("[all done]")
'''


def _r(v):
    if not isinstance(v, str): return v
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--out", default="data/sota_runs/dense")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    s = cfg["ssh_servers"][0]
    pwd = _r(s.get("target_password", "")) or os.environ.get("SSH_PRIMARY_PASSWORD", "")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(s["target_host"], port=s["target_port"],
                username=s["target_user"], password=pwd, timeout=30)

    visdom_root = s["deployment"]["visdom_data"]
    remote_script = "/tmp/extract_visdom_dense.py"
    payload = REMOTE_SCRIPT.format(visdom_root=visdom_root)

    sftp = ssh.open_sftp()
    with sftp.file(remote_script, "w") as f:
        f.write(payload)
    sftp.close()
    print(f"[upload] {remote_script}")

    cmd = (
        "source ~/miniconda3/etc/profile.d/conda.sh && "
        "conda activate mrag_worker && "
        f"python {remote_script}"
    )
    _, stdout, stderr = ssh.exec_command(cmd, timeout=7200)
    while True:
        line = stdout.readline()
        if not line: break
        print(line.rstrip())
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip(): print("STDERR:", err[:2000])

    # Pull files
    os.makedirs(args.out, exist_ok=True)
    sftp = ssh.open_sftp()
    remote_dense = f"{visdom_root}/sota_dense"
    try:
        files = sftp.listdir(remote_dense)
    except Exception as e:
        print(f"[warn] list {remote_dense}: {e}"); files = []
    for f in files:
        rp = f"{remote_dense}/{f}"
        lp = os.path.join(args.out, f)
        try:
            sftp.get(rp, lp)
            print(f"[pull] {f} ({os.path.getsize(lp)} B)")
        except Exception as e:
            print(f"[warn] pull {f} failed: {e}")
    sftp.close()
    ssh.close()


if __name__ == "__main__":
    main()
