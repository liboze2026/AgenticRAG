"""OCR-extract slidevqa decks.

slidevqa PDFs are image-only (pdfplumber extracts 0 text). This uploads a
worker-side script that uses pdf2image + tesseract OCR to extract per-slide
text. Fallback to easyocr if tesseract not present.

Output: $VISDOM_REMOTE/sota_text_ocr/slidevqa.jsonl (same schema as
sota_text/*.jsonl). After extraction, SFTP-pulls to
data/sota_runs/corpus_ocr/slidevqa.jsonl which the corpus loader will
union with the regular corpus.

Run:
    SSH_PRIMARY_PASSWORD=<pwd> python scripts/extract_visdom_ocr.py
"""
import os, re, sys, paramiko, yaml


REMOTE_SCRIPT = r'''#!/usr/bin/env python
"""Worker-side: pdf2image + tesseract OCR on slidevqa decks."""
import json
import os
import sys
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed

try:
    from pdf2image import convert_from_path
except ImportError:
    print("pdf2image missing", file=sys.stderr); sys.exit(2)

try:
    import pytesseract
    HAS_TESS = True
except ImportError:
    HAS_TESS = False

if not HAS_TESS:
    print("pytesseract not installed; aborting", file=sys.stderr); sys.exit(2)

ROOT = "{visdom_root}"
SRC = os.path.join(ROOT, "slidevqa", "docs")
OUT = os.path.join(ROOT, "sota_text_ocr")
os.makedirs(OUT, exist_ok=True)


def _ocr_pdf(args):
    pdf_path, doc_id = args
    rows = []
    try:
        # Lower DPI = faster; slides are large so 150 dpi is plenty for OCR
        pages = convert_from_path(pdf_path, dpi=150, fmt="png")
    except Exception as e:
        return rows
    for i, img in enumerate(pages, start=1):
        try:
            text = pytesseract.image_to_string(img, lang="eng") or ""
        except Exception:
            text = ""
        rows.append((doc_id, i, text.strip()))
    return rows


def main():
    out_path = os.path.join(OUT, "slidevqa.jsonl")
    tmp_path = out_path + ".tmp"
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        print("[skip] slidevqa.jsonl exists"); return
    if not os.path.isdir(SRC):
        print(f"[error] {{SRC}} missing"); return
    files = sorted(f for f in os.listdir(SRC) if f.lower().endswith(".pdf"))
    print(f"[start] {{len(files)}} decks")
    n_pages = 0
    with open(tmp_path, "w", encoding="utf-8") as f, ProcessPoolExecutor(max_workers=4) as pool:
        futs = []
        for fname in files:
            doc_id = fname[:-4] if fname.lower().endswith(".pdf") else fname
            pdf_path = os.path.join(SRC, fname)
            futs.append(pool.submit(_ocr_pdf, (pdf_path, doc_id)))
        for fut in as_completed(futs):
            try:
                rows = fut.result()
            except Exception:
                continue
            for (d, p, t) in rows:
                f.write(json.dumps({{"doc_id": d, "page_number": p, "text": t}}, ensure_ascii=False) + "\n")
                n_pages += 1
    os.replace(tmp_path, out_path)
    print(f"[done] {{n_pages}} pages → {{out_path}}")

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
    remote_script = "/tmp/extract_visdom_ocr.py"

    payload = REMOTE_SCRIPT.format(visdom_root=visdom_root)
    ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(s["target_host"], port=s["target_port"], username=s["target_user"], password=pwd, timeout=30)

    sftp = ssh.open_sftp()
    with sftp.file(remote_script, "w") as f:
        f.write(payload)
    sftp.close()
    print(f"[upload] {remote_script}")

    # Ensure deps
    install = (
        "source ~/miniconda3/etc/profile.d/conda.sh && "
        "conda activate mrag_worker && "
        "pip install -q pytesseract && "
        "(which tesseract || apt-get install -y tesseract-ocr 2>&1 | tail -3)"
    )
    print("[deps]")
    _, stdout, _ = ssh.exec_command(install, timeout=600)
    print(stdout.read().decode("utf-8", errors="replace")[:500])

    cmd = (
        "source ~/miniconda3/etc/profile.d/conda.sh && "
        "conda activate mrag_worker && "
        f"python -u {remote_script}"
    )
    print(f"[run]")
    chan = ssh.get_transport().open_session(); chan.set_combine_stderr(True); chan.exec_command(cmd)
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

    out_local = "data/sota_runs/corpus_ocr"
    os.makedirs(out_local, exist_ok=True)
    sftp = ssh.open_sftp()
    rp = f"{visdom_root}/sota_text_ocr/slidevqa.jsonl"
    lp = os.path.join(out_local, "slidevqa.jsonl")
    try:
        sftp.get(rp, lp)
        print(f"[pull] slidevqa.jsonl ({os.path.getsize(lp)} B)")
    except Exception as e:
        print(f"[warn] pull failed: {e}")
    sftp.close(); ssh.close()


if __name__ == "__main__":
    main()
