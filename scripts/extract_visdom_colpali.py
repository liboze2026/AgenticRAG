"""Pre-compute ColPali multi-vector embeddings for slidevqa decks.

ColPali outputs (N_patches, D=128) per page. We save:
  data/sota_runs/colpali/slidevqa.npz  (stacked float16, shape (M, P, D))
  data/sota_runs/colpali/slidevqa.keys.jsonl  (M rows: doc_id, page, n_patches)
  data/sota_runs/colpali/slidevqa.meta.json   (max_patches, dim, dtype)

Pages are zero-padded to max_patches across the subset to allow stacking.

Runs on remote (model cached at vidore/colpali-v1.2).
"""
try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError: pass
import os, re, sys, paramiko, yaml


REMOTE_SCRIPT = r'''#!/usr/bin/env python
"""Worker-side ColPali encode for slidevqa decks. Detached process."""
import json
import os
import sys
import gc

import numpy as np
import torch

try:
    from pdf2image import convert_from_path
    from colpali_engine.models import ColPali, ColPaliProcessor
except ImportError as e:
    print(f"missing: {{e}}", file=sys.stderr); sys.exit(2)

ROOT = "{visdom_root}"
SRC = os.path.join(ROOT, "slidevqa", "docs")
OUT = os.path.join(ROOT, "sota_colpali")
os.makedirs(OUT, exist_ok=True)

# Use worker's cached colpali snapshot
from pathlib import Path
cache_root = Path(os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))) / "hub"
snap_root = cache_root / "models--vidore--colpali-v1.2" / "snapshots"
if snap_root.exists():
    snaps = list(snap_root.iterdir())
    model_path = str(snaps[0]) if snaps else "vidore/colpali-v1.2"
else:
    model_path = "vidore/colpali-v1.2"
print(f"[load] {{model_path}}")

model = ColPali.from_pretrained(model_path, device_map="auto").eval()
processor = ColPaliProcessor.from_pretrained(model_path)
device = next(model.parameters()).device
print(f"[loaded] device={{device}}")


def _encode_batch(images):
    inputs = processor.process_images(images)
    inputs = {{k: v.to(device) for k, v in inputs.items()}}
    with torch.no_grad():
        emb = model(**inputs)
    return emb.cpu().numpy()


def main():
    out_npz = os.path.join(OUT, "slidevqa.npz")
    out_keys = os.path.join(OUT, "slidevqa.keys.jsonl")
    out_meta = os.path.join(OUT, "slidevqa.meta.json")
    if os.path.exists(out_npz) and os.path.getsize(out_npz) > 1_000_000:
        print("[skip] slidevqa already done"); return
    files = sorted(f for f in os.listdir(SRC) if f.lower().endswith(".pdf"))
    print(f"[start] {{len(files)}} decks")
    keys = []
    raw_embs = []
    n_pages = 0
    BATCH = 1
    batch_imgs = []
    batch_keys = []

    def flush():
        nonlocal batch_imgs, batch_keys, n_pages
        if not batch_imgs:
            return
        try:
            embs = _encode_batch(batch_imgs)
        except torch.cuda.OutOfMemoryError:
            print("[oom] reduce DPI?"); return
        for j, (k, e) in enumerate(zip(batch_keys, embs)):
            keys.append(k)
            raw_embs.append(e.astype("float16"))
        n_pages += len(batch_imgs)
        batch_imgs = []
        batch_keys = []
        gc.collect()
        torch.cuda.empty_cache()

    for j, fname in enumerate(files):
        doc_id = fname[:-4] if fname.lower().endswith(".pdf") else fname
        try:
            pages = convert_from_path(os.path.join(SRC, fname), dpi=120, fmt="png")
        except Exception as e:
            print(f"[err] {{fname}}: {{e}}"); continue
        for i, img in enumerate(pages, start=1):
            batch_imgs.append(img)
            batch_keys.append((doc_id, i))
            if len(batch_imgs) >= BATCH:
                flush()
        if (j + 1) % 10 == 0:
            print(f"[progress] {{j+1}}/{{len(files)}} pages={{n_pages}}")
    flush()

    if not raw_embs:
        print("[empty]"); return
    max_p = max(e.shape[0] for e in raw_embs)
    dim = raw_embs[0].shape[1]
    print(f"[stack] {{len(raw_embs)}} pages, max_patches={{max_p}}, dim={{dim}}")
    stacked = np.zeros((len(raw_embs), max_p, dim), dtype="float16")
    n_patches = []
    for i, e in enumerate(raw_embs):
        n = e.shape[0]
        stacked[i, :n] = e
        n_patches.append(int(n))
    np.savez_compressed(out_npz, embs=stacked)
    with open(out_keys, "w", encoding="utf-8") as f:
        for ((d, p), n) in zip(keys, n_patches):
            f.write(json.dumps({{"doc_id": d, "page_number": p, "n_patches": n}}, ensure_ascii=False) + "\n")
    with open(out_meta, "w", encoding="utf-8") as f:
        json.dump({{"max_patches": int(max_p), "dim": int(dim), "dtype": "float16"}}, f)
    print(f"[done] saved → {{out_npz}}")


if __name__ == "__main__":
    main()
'''


def _r(v):
    if not isinstance(v, str): return v
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), v)


def main():
    cfg = yaml.safe_load(open("config/default.yaml", encoding="utf-8"))
    s = cfg["ssh_servers"][0]
    pwd = _r(s.get("target_password", "")) or os.environ.get("SSH_PRIMARY_PASSWORD", "")
    visdom_root = s["deployment"]["visdom_data"]
    hf_home = s["deployment"].get("hf_home", "")
    remote_script = "/tmp/extract_visdom_colpali.py"

    payload = REMOTE_SCRIPT.format(visdom_root=visdom_root)
    ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(s["target_host"], port=s["target_port"], username=s["target_user"], password=pwd, timeout=30)

    sftp = ssh.open_sftp()
    with sftp.file(remote_script, "w") as f:
        f.write(payload)
    sftp.close()
    print(f"[upload] {remote_script}")

    log_path = "/tmp/colpali_slidevqa.log"
    hf_env = f"HF_HOME={hf_home} " if hf_home else ""
    cmd = (
        f"bash -c 'setsid bash -c \""
        f"source ~/miniconda3/etc/profile.d/conda.sh && "
        f"conda activate mrag_worker && "
        f"{hf_env}HF_ENDPOINT=https://hf-mirror.com HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "
        f"python -u {remote_script}\" "
        f"</dev/null > {log_path} 2>&1 & disown; sleep 0.5; echo launched'"
    )
    print("[launch detached]")
    ssh.exec_command(cmd, timeout=10)
    print(f"  log: {log_path}")
    ssh.close()


if __name__ == "__main__":
    main()
