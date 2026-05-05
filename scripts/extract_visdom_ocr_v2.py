"""OCR extract slidevqa via easyocr (GPU-accelerated, pure Python, no apt)."""
try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError: pass
import os, re, sys, paramiko, yaml


REMOTE_SCRIPT = r'''#!/usr/bin/env python
import json
import os
import sys

try:
    from pdf2image import convert_from_path
except ImportError:
    print("pdf2image missing", file=sys.stderr); sys.exit(2)
try:
    import easyocr
    import torch
except ImportError as e:
    print(f"easyocr missing: {{e}}", file=sys.stderr); sys.exit(2)

ROOT = "{visdom_root}"
SRC = os.path.join(ROOT, "slidevqa", "docs")
OUT = os.path.join(ROOT, "sota_text_ocr")
os.makedirs(OUT, exist_ok=True)

print(f"[load] easyocr eng device cuda={{torch.cuda.is_available()}}")
reader = easyocr.Reader(["en"], gpu=torch.cuda.is_available())
print("[loaded]")


def main():
    out_path = os.path.join(OUT, "slidevqa.jsonl")
    tmp_path = out_path + ".tmp"
    if os.path.isfile(out_path) and os.path.getsize(out_path) > 1_000_000:
        # already has real (non-empty) content
        print("[skip] slidevqa.jsonl looks populated, exiting"); return
    if not os.path.isdir(SRC):
        print(f"[error] missing {{SRC}}"); return
    files = sorted(f for f in os.listdir(SRC) if f.lower().endswith(".pdf"))
    print(f"[start] {{len(files)}} decks")
    n_pages = 0
    n_chars = 0
    import numpy as np
    with open(tmp_path, "w", encoding="utf-8") as out:
        for j, fname in enumerate(files):
            doc_id = fname[:-4] if fname.lower().endswith(".pdf") else fname
            try:
                pages = convert_from_path(os.path.join(SRC, fname), dpi=150, fmt="png")
            except Exception as e:
                print(f"[err] {{fname}}: {{e}}"); continue
            for i, img in enumerate(pages, start=1):
                arr = np.array(img)
                try:
                    res = reader.readtext(arr, detail=0, paragraph=True) or []
                    text = " ".join(res)
                except Exception:
                    text = ""
                out.write(json.dumps({{"doc_id": doc_id, "page_number": i, "text": text}}, ensure_ascii=False) + "\n")
                n_pages += 1
                n_chars += len(text)
            if (j + 1) % 10 == 0:
                print(f"[progress] {{j+1}}/{{len(files)}} pages={{n_pages}} chars={{n_chars}}")
    os.replace(tmp_path, out_path)
    print(f"[done] {{n_pages}} pages, {{n_chars}} chars → {{out_path}}")

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
    remote_script = "/tmp/extract_visdom_ocr_v2.py"

    payload = REMOTE_SCRIPT.format(visdom_root=visdom_root)
    ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(s["target_host"], port=s["target_port"], username=s["target_user"], password=pwd, timeout=30)

    sftp = ssh.open_sftp()
    with sftp.file(remote_script, "w") as f:
        f.write(payload)
    sftp.close()
    print(f"[upload] {remote_script}")

    install = (
        "source ~/miniconda3/etc/profile.d/conda.sh && "
        "conda activate mrag_worker && "
        "HF_ENDPOINT=https://hf-mirror.com pip install -q easyocr 2>&1 | tail -5"
    )
    print("[deps]")
    _, stdout, _ = ssh.exec_command(install, timeout=900)
    print(stdout.read().decode("utf-8", errors="replace")[:500])

    # Remove any prior empty slidevqa.jsonl so the new run actually writes
    ssh.exec_command(f"rm -f {visdom_root}/sota_text_ocr/slidevqa.jsonl")

    log_path = "/tmp/easyocr_slidevqa.log"
    # Wrap in setsid so the child fully detaches; redirect stdin to /dev/null
    cmd = (
        "bash -c 'setsid bash -c \""
        "source ~/miniconda3/etc/profile.d/conda.sh && "
        "conda activate mrag_worker && "
        "HF_ENDPOINT=https://hf-mirror.com HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 "
        f"python -u {remote_script}\" "
        f"</dev/null > {log_path} 2>&1 & disown; sleep 0.5; echo launched'"
    )
    print("[launch detached]")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    try:
        out = stdout.read(timeout=8) if hasattr(stdout, 'read') else b""
    except Exception:
        out = b""
    print(f"  log: {log_path}")
    ssh.close()


if __name__ == "__main__":
    main()
