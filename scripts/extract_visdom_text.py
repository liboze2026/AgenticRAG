"""Run via SSH on the active server: extract per-page text from each VisDoM
PDF using pdfplumber, dump as JSONL files (one per subset).

Output schema (one row = one page):
    {"doc_id": ..., "page_number": int, "text": ...}

Output written to remote $VISDOM_REMOTE/sota_text/<subset>.jsonl.

This script is uploaded to the worker and executed there because the PDFs
are 1-2 GB total and live on the worker filesystem. Pulling them locally
would be slow + duplicate disk usage. After extraction, only the small
JSONL files (~100 MB total expected) are SFTP-pulled to local machine.

Run locally:
    SSH_PRIMARY_PASSWORD=<pwd> python scripts/extract_visdom_text.py
"""
import argparse
import os
import re
import sys
import time

import paramiko
import yaml


REMOTE_SCRIPT = r'''#!/usr/bin/env python
"""Worker-side text extractor. Stays self-contained — only pdfplumber required."""
import json
import os
import sys
import traceback

try:
    import pdfplumber
except ImportError:
    print("pdfplumber not available on worker, exiting", file=sys.stderr)
    sys.exit(2)

ROOT = "{visdom_root}"
OUT  = "{out_dir}"
os.makedirs(OUT, exist_ok=True)

SUBSET_DIRS = {{
    "feta_tab":    "feta_tab/docs",
    "paper_tab":   "paper_tab/docs",
    "scigraphvqa": "scigraphvqa/docs",
    "slidevqa":    "slidevqa/docs",
    "spiqa":       "spiqa/docs",
}}

def doc_id_from(name):
    return name[:-4] if name.lower().endswith(".pdf") else name

def extract_one(pdf_path):
    """Yield (page_number, text) for each page; never raise."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                try:
                    t = page.extract_text() or ""
                except Exception:
                    t = ""
                yield i, t.strip()
    except Exception:
        return

for subset, rel in SUBSET_DIRS.items():
    src = os.path.join(ROOT, rel)
    out_path = os.path.join(OUT, subset + ".jsonl")
    if not os.path.isdir(src):
        print(f"[skip] {{subset}}: {{src}} not a directory")
        continue
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        print(f"[skip] {{subset}}: {{out_path}} already exists")
        continue
    files = sorted(os.listdir(src))
    files = [f for f in files if f.lower().endswith(".pdf")]
    print(f"[start] {{subset}}: {{len(files)}} pdfs → {{out_path}}")
    n_pages = 0
    n_chars = 0
    n_errors = 0
    with open(out_path, "w", encoding="utf-8") as out:
        for fname in files:
            doc_id = doc_id_from(fname)
            pdf_path = os.path.join(src, fname)
            had = False
            for page_num, text in extract_one(pdf_path):
                had = True
                n_pages += 1
                n_chars += len(text)
                out.write(json.dumps({{
                    "doc_id": doc_id,
                    "page_number": page_num,
                    "text": text,
                }}, ensure_ascii=False) + "\n")
            if not had:
                n_errors += 1
    print(f"[done] {{subset}}: {{n_pages}} pages, {{n_chars}} chars, {{n_errors}} errors")
'''


def _resolve_env(value: str) -> str:
    if not isinstance(value, str):
        return value
    pattern = re.compile(r"\$\{(\w+)\}")
    return pattern.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--out", default="data/sota_runs/corpus")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    server = cfg["ssh_servers"][0]
    pwd = _resolve_env(server.get("target_password", "")) or os.environ.get("SSH_PRIMARY_PASSWORD", "")
    if not pwd:
        print("SSH_PRIMARY_PASSWORD not set", file=sys.stderr); sys.exit(1)

    visdom_root = server["deployment"]["visdom_data"]
    remote_script = "/tmp/extract_visdom_text.py"
    remote_out = f"{visdom_root}/sota_text"

    payload = REMOTE_SCRIPT.format(visdom_root=visdom_root, out_dir=remote_out)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(server["target_host"], port=server["target_port"],
                username=server["target_user"], password=pwd, timeout=30)

    sftp = ssh.open_sftp()
    with sftp.file(remote_script, "w") as f:
        f.write(payload)
    sftp.close()
    print(f"[upload] script → {remote_script}")

    # Run in conda env where pdfplumber lives. The mrag_worker env on autodl
    # has pdfplumber pre-installed for the layout processor.
    cmd = (
        "source ~/miniconda3/etc/profile.d/conda.sh && "
        "conda activate mrag_worker && "
        f"python {remote_script}"
    )
    print(f"[run] {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=3600)

    # Stream output
    while True:
        line = stdout.readline()
        if not line:
            break
        print(line.rstrip())
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err[:2000])

    # Pull resulting JSONLs locally
    local_out = args.out
    os.makedirs(local_out, exist_ok=True)
    sftp = ssh.open_sftp()
    try:
        files = sftp.listdir(remote_out)
    except Exception as e:
        print(f"[warn] could not list {remote_out}: {e}")
        files = []
    print(f"[remote out] {files}")
    for f in files:
        if not f.endswith(".jsonl"):
            continue
        remote_path = f"{remote_out}/{f}"
        local_path = os.path.join(local_out, f)
        try:
            sftp.get(remote_path, local_path)
            size = os.path.getsize(local_path)
            print(f"[pull] {f} ({size} B)")
        except Exception as e:
            print(f"[warn] pull {f} failed: {e}")
    sftp.close()
    ssh.close()


if __name__ == "__main__":
    main()
