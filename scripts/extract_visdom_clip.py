"""Pre-compute CLIP image embeddings for slidevqa decks.

Runs on remote worker GPU. For each slidevqa PDF page:
  pdf2image (DPI=150) → PIL → CLIP image encoder → 512-d vector

Saves to $VISDOM_REMOTE/sota_clip/slidevqa.npz + .keys.jsonl, then
SFTP-pulls to data/sota_runs/clip/slidevqa.*

Model: openai/clip-vit-base-patch32 (smallest, fastest, ~150 MB).
Downloaded via HF mirror (already proven to work for bge).
"""
try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError: pass
import os, re, sys, paramiko, yaml


REMOTE_SCRIPT = r'''#!/usr/bin/env python
import json
import os
import sys
import io

try:
    import numpy as np
    import torch
    from pdf2image import convert_from_path
    from transformers import CLIPModel, CLIPProcessor
except ImportError as e:
    print(f"missing: {{e}}", file=sys.stderr); sys.exit(2)

ROOT = "{visdom_root}"
SRC = os.path.join(ROOT, "slidevqa", "docs")
OUT = os.path.join(ROOT, "sota_clip")
os.makedirs(OUT, exist_ok=True)

MODEL = "openai/clip-vit-base-patch32"
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[load] {{MODEL}} on {{device}}")
model = CLIPModel.from_pretrained(MODEL).to(device).eval()
processor = CLIPProcessor.from_pretrained(MODEL)
print("[loaded]")


def main():
    out_npz = os.path.join(OUT, "slidevqa.npz")
    out_keys = os.path.join(OUT, "slidevqa.keys.jsonl")
    if os.path.exists(out_npz) and os.path.getsize(out_npz) > 1_000_000:
        print("[skip] slidevqa already done"); return
    files = sorted(f for f in os.listdir(SRC) if f.lower().endswith(".pdf"))
    print(f"[start] {{len(files)}} decks")
    keys = []
    embs_list = []
    n_pages = 0
    BATCH = 16
    batch_imgs = []
    batch_keys = []

    def flush():
        nonlocal batch_imgs, batch_keys, n_pages
        if not batch_imgs:
            return
        with torch.no_grad():
            inputs = processor(images=batch_imgs, return_tensors="pt").to(device)
            feats = model.get_image_features(**inputs)
            feats = torch.nn.functional.normalize(feats, dim=-1).cpu().numpy()
        embs_list.append(feats)
        keys.extend(batch_keys)
        n_pages += len(batch_imgs)
        batch_imgs = []
        batch_keys = []

    for j, fname in enumerate(files):
        doc_id = fname[:-4] if fname.lower().endswith(".pdf") else fname
        try:
            pages = convert_from_path(os.path.join(SRC, fname), dpi=150, fmt="png")
        except Exception as e:
            print(f"[err] {{fname}}: {{e}}"); continue
        for i, img in enumerate(pages, start=1):
            batch_imgs.append(img)
            batch_keys.append((doc_id, i))
            if len(batch_imgs) >= BATCH:
                flush()
        if (j + 1) % 20 == 0:
            print(f"[progress] {{j+1}}/{{len(files)}} pages={{n_pages}}")
    flush()

    if not embs_list:
        print("[empty]"); return
    embs = np.concatenate(embs_list, axis=0).astype("float32")
    np.savez_compressed(out_npz, embs=embs)
    with open(out_keys, "w", encoding="utf-8") as f:
        for (d, p) in keys:
            f.write(json.dumps({{"doc_id": d, "page_number": p}}, ensure_ascii=False) + "\n")
    print(f"[done] {{embs.shape}} → {{out_npz}}")


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
    remote_script = "/tmp/extract_visdom_clip.py"

    payload = REMOTE_SCRIPT.format(visdom_root=visdom_root)
    ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(s["target_host"], port=s["target_port"], username=s["target_user"], password=pwd, timeout=30)

    sftp = ssh.open_sftp()
    with sftp.file(remote_script, "w") as f:
        f.write(payload)
    sftp.close()
    print(f"[upload] {remote_script}")

    log_path = "/tmp/clip_slidevqa.log"
    cmd = (
        "bash -c 'setsid bash -c \""
        "source ~/miniconda3/etc/profile.d/conda.sh && "
        "conda activate mrag_worker && "
        "HF_ENDPOINT=https://hf-mirror.com HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 "
        f"python -u {remote_script}\" "
        f"</dev/null > {log_path} 2>&1 & disown; sleep 0.5; echo launched'"
    )
    print("[launch detached]")
    ssh.exec_command(cmd, timeout=10)
    print(f"  log: {log_path}")
    ssh.close()


if __name__ == "__main__":
    main()
