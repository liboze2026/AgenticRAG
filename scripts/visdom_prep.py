"""
VisDoM SPIQA mini-reproduction prep:
1. Pick top-K papers by query count
2. SFTP-pull their PDFs from remote
3. Pull queries pointing to those papers
4. Emit eval JSON for AgenticRAG
"""
import os
import sys
import io
import json
import csv
import collections
from dotenv import load_dotenv
import paramiko

# UTF-8 stdout on Windows
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT, ".env"))

KEY = os.path.expanduser(os.environ.get("SSH_BASTION_KEY", ""))
PASSWORD = os.environ.get("SSH_TARGET_PASSWORD", "")

REMOTE_BASE = "/home/bzli/lbz/data/VisDoM-main"
REMOTE_CSV = f"{REMOTE_BASE}/spiqa/spiqa.csv"
REMOTE_DOCS = f"{REMOTE_BASE}/spiqa/docs"

LOCAL_DIR = os.path.join(PROJECT, "data", "visdom_spiqa_mini")
os.makedirs(LOCAL_DIR, exist_ok=True)

TOP_N_PAPERS = 3
TARGET_DOCS = None  # filled after counting
MAX_PAGES_PER_DOC = 12  # cap to avoid long runs on busy GPU

# --- 1. Connect ---
bastion = paramiko.SSHClient()
bastion.set_missing_host_key_policy(paramiko.AutoAddPolicy())
bastion.connect("vlab.ustc.edu.cn", port=22, username="ubuntu",
                key_filename=KEY, look_for_keys=False, allow_agent=False, timeout=15)

chan = bastion.get_transport().open_channel("direct-tcpip", ("202.38.68.70", 2266), ("127.0.0.1", 0))
target = paramiko.SSHClient()
target.set_missing_host_key_policy(paramiko.AutoAddPolicy())
target.connect("202.38.68.70", port=2266, username="bzli",
               password=PASSWORD, sock=chan, timeout=25,
               look_for_keys=False, allow_agent=False)
print("[+] Connected")

# --- 2. Pull CSV via sftp ---
sftp = target.open_sftp()
local_csv = os.path.join(LOCAL_DIR, "spiqa.csv")
sftp.get(REMOTE_CSV, local_csv)
print(f"[+] CSV downloaded: {local_csv}")

# --- 3. Parse + pick top papers ---
with open(local_csv, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

ctr = collections.Counter(r["doc_id"] for r in rows)
top = [doc for doc, _ in ctr.most_common(TOP_N_PAPERS)]
TARGET_DOCS = set(top)
print(f"[+] Top {TOP_N_PAPERS} papers: {top}")

selected_rows = [r for r in rows if r["doc_id"] in TARGET_DOCS]
print(f"[+] Queries pointing to these {TOP_N_PAPERS} papers: {len(selected_rows)}")

# --- 4. Pull PDFs ---
pdf_dir = os.path.join(LOCAL_DIR, "pdfs")
os.makedirs(pdf_dir, exist_ok=True)
for doc_id in top:
    remote = f"{REMOTE_DOCS}/{doc_id}.pdf"
    local = os.path.join(pdf_dir, f"{doc_id}.pdf")
    if not os.path.exists(local):
        sftp.get(remote, local)
        size = os.path.getsize(local)
        print(f"  {doc_id}.pdf  {size//1024} KB")
    else:
        print(f"  {doc_id}.pdf  (cached)")

sftp.close()

# --- 5. Pull metadata via remote python ---
def remote_pdf_pages(doc_id):
    """Get page count via remote pdfinfo."""
    _, stdout, _ = target.exec_command(f"pdfinfo {REMOTE_DOCS}/{doc_id}.pdf | grep Pages | awk '{{print $2}}'")
    return int(stdout.read().decode().strip() or 0)

doc_meta = {}
for doc_id in top:
    pages = remote_pdf_pages(doc_id)
    doc_meta[doc_id] = pages
    print(f"  {doc_id}  pages={pages}")

target.close()
bastion.close()

# --- 6. Emit eval JSON for AgenticRAG ---
# Format: [{"query": ..., "relevant": ["doc_id"]}, ...]
# Eval is page-agnostic (relevant is just doc_id since SPIQA doesn't give exact page in csv)
eval_json = []
selected_for_eval = selected_rows[:60]  # cap at 60 for runtime
for r in selected_for_eval:
    eval_json.append({
        "q_id": r["q_id"],
        "query": r["question"],
        "target_doc": r["doc_id"],
        "reference_figure": r["reference_figure"],
        "paper_title": r["paper_title"],
        "relevant": [r["doc_id"]],  # AgenticRAG eval uses relevant list
    })

eval_path = os.path.join(LOCAL_DIR, "eval.json")
with open(eval_path, "w", encoding="utf-8") as f:
    json.dump(eval_json, f, ensure_ascii=False, indent=2)
print(f"[+] Eval JSON saved: {eval_path}  ({len(eval_json)} queries)")

# --- 7. Save manifest ---
manifest = {
    "dataset": "VisDoM/SPIQA",
    "subset_strategy": f"top {TOP_N_PAPERS} papers by query count",
    "papers": top,
    "doc_pages": doc_meta,
    "queries_total_in_subset": len(selected_rows),
    "queries_in_eval": len(eval_json),
    "csv_source": REMOTE_CSV,
    "pdf_source": REMOTE_DOCS,
}
with open(os.path.join(LOCAL_DIR, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print("[+] Manifest saved.")
print("\n=== DONE ===")
print(f"PDFs:      {pdf_dir}/")
print(f"Eval:      {eval_path}")
print(f"Manifest:  {os.path.join(LOCAL_DIR, 'manifest.json')}")
