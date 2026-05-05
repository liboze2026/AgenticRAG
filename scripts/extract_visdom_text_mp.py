"""Faster: multi-process VisDoM text extraction on remote.

Uploads a worker-side script that extracts each subset in parallel using
ProcessPoolExecutor (one process per subset, default 5 workers). Each
subset writes to its own jsonl atomically (tmp file + rename).

Idempotent: if <subset>.jsonl already exists and is non-empty, that subset
is skipped. Allows safe restart after kill.
"""
import argparse
import os
import re
import sys

import paramiko
import yaml
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


REMOTE_SCRIPT = r'''#!/usr/bin/env python
"""Multi-process worker-side text extractor."""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

try:
    import pdfplumber
except ImportError:
    print("pdfplumber missing", file=sys.stderr); sys.exit(2)

ROOT = "{visdom_root}"
OUT  = os.path.join(ROOT, "sota_text")
os.makedirs(OUT, exist_ok=True)

SUBSET_DIRS = {{
    "feta_tab":    "feta_tab/docs",
    "paper_tab":   "paper_tab/docs",
    "scigraphvqa": "scigraphvqa/docs",
    "slidevqa":    "slidevqa/docs",
    "spiqa":       "spiqa/docs",
}}


def _extract_pdf(args):
    pdf_path, doc_id = args
    rows = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                try:
                    t = page.extract_text() or ""
                except Exception:
                    t = ""
                rows.append((doc_id, i, t.strip()))
    except Exception:
        pass
    return rows


def _process_subset(subset, rel):
    src = os.path.join(ROOT, rel)
    out_path = os.path.join(OUT, subset + ".jsonl")
    tmp_path = out_path + ".tmp"
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        print(f"[skip] {{subset}} already done")
        return
    if not os.path.isdir(src):
        print(f"[skip] {{subset}}: no dir")
        return
    files = sorted(f for f in os.listdir(src) if f.lower().endswith(".pdf"))
    print(f"[start] {{subset}}: {{len(files)}} pdfs")
    n_pages = 0
    with open(tmp_path, "w", encoding="utf-8") as f:
        # within each subset, process pdfs serially (avoids over-subscribing cores
        # since we already parallelize across subsets)
        for fname in files:
            doc_id = fname[:-4] if fname.lower().endswith(".pdf") else fname
            pdf_path = os.path.join(src, fname)
            rows = _extract_pdf((pdf_path, doc_id))
            for (d, p, t) in rows:
                f.write(json.dumps({{"doc_id": d, "page_number": p, "text": t}}, ensure_ascii=False) + "\n")
                n_pages += 1
    os.replace(tmp_path, out_path)
    print(f"[done] {{subset}}: {{n_pages}} pages → {{out_path}}")


def main():
    # Run the 5 subsets in parallel (cap at 5 workers; pdfplumber is CPU-bound).
    with ProcessPoolExecutor(max_workers=5) as pool:
        futs = [pool.submit(_process_subset, s, r) for s, r in SUBSET_DIRS.items()]
        for fut in as_completed(futs):
            try:
                fut.result()
            except Exception as e:
                print(f"[error] {{type(e).__name__}}: {{e}}")
    print("[all done]")


if __name__ == "__main__":
    main()
'''


def _r(v):
    if not isinstance(v, str): return v
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--out", default="data/sota_runs/corpus")
    ap.add_argument("--kill_existing", action="store_true",
                    help="pkill any running extract_visdom_text.py first")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    s = cfg["ssh_servers"][0]
    pwd = _r(s.get("target_password", "")) or os.environ.get("SSH_PRIMARY_PASSWORD", "")
    visdom_root = s["deployment"]["visdom_data"]
    remote_script = "/tmp/extract_visdom_text_mp.py"

    payload = REMOTE_SCRIPT.format(visdom_root=visdom_root)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(s["target_host"], port=s["target_port"],
                username=s["target_user"], password=pwd, timeout=30)

    if args.kill_existing:
        ssh.exec_command("pkill -f extract_visdom_text || true")
        # wait so the lock on tmp files clears
        ssh.exec_command("sleep 2")

    sftp = ssh.open_sftp()
    with sftp.file(remote_script, "w") as f:
        f.write(payload)
    sftp.close()
    print(f"[upload] {remote_script}")

    cmd = (
        "source ~/miniconda3/etc/profile.d/conda.sh && "
        "conda activate mrag_worker && "
        f"python -u {remote_script}"
    )
    print(f"[run] {cmd}")
    chan = ssh.get_transport().open_session()
    chan.set_combine_stderr(True)
    chan.exec_command(cmd)
    while True:
        if chan.recv_ready():
            data = chan.recv(4096).decode("utf-8", errors="replace")
            sys.stdout.write(data); sys.stdout.flush()
        if chan.exit_status_ready():
            while chan.recv_ready():
                data = chan.recv(4096).decode("utf-8", errors="replace")
                sys.stdout.write(data); sys.stdout.flush()
            break
    print(f"[remote exit] {chan.recv_exit_status()}")

    # Pull results
    os.makedirs(args.out, exist_ok=True)
    sftp = ssh.open_sftp()
    remote_out = f"{visdom_root}/sota_text"
    try:
        files = sftp.listdir(remote_out)
    except Exception as e:
        print(f"[warn] list {remote_out}: {e}"); files = []
    for f in files:
        if not f.endswith(".jsonl"):
            continue
        rp = f"{remote_out}/{f}"
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
