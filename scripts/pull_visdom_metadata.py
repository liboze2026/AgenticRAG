"""Pull VisDoM-main subset CSVs from remote server, convert to queries.jsonl
under data/sota_runs/datasets/<subset>/queries.jsonl.

Each subset CSV has its own columns. The converter extracts:
  query_id        ← q_id
  query           ← question
  gold_doc_ids    ← [doc_path basename without .pdf]  (page-recall = doc match)
  gold_page_numbers ← [evidence_pages] for slidevqa, [1] otherwise (doc-level)
  metadata.candidate_docs ← parsed `documents` column (per-query candidate pool)

For slidevqa, evidence_pages is a Python-style list literal like "[3, 7]".
We parse it best-effort. Other subsets currently lack page-level gold; we
record page=1 and rely on document-level Recall for those subsets, which
matches one of the metrics reported in the VisDoM paper.

Run:
    SSH_PRIMARY_PASSWORD=<pwd> python scripts/pull_visdom_metadata.py
"""
import argparse
import ast
import csv
import io
import json
import os
import re
import sys
from typing import Any, Dict, List

import paramiko
import yaml
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _resolve_env(value: str) -> str:
    if not isinstance(value, str):
        return value
    pattern = re.compile(r"\$\{(\w+)\}")
    return pattern.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value)


def _parse_list_literal(s: str) -> List:
    if not s or not isinstance(s, str):
        return []
    try:
        v = ast.literal_eval(s)
        return v if isinstance(v, list) else []
    except Exception:
        return []


def _doc_id_from_path(path: str) -> str:
    """e.g. '1809.01202.pdf' → '1809.01202'.
    For slidevqa: 'foo_95.pdf' → 'foo_95'."""
    name = os.path.basename(path or "")
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    return name


def _convert_row(subset: str, row: Dict[str, str]) -> Dict[str, Any]:
    q_id = row.get("q_id") or row.get("query_id") or ""
    question = row.get("question") or row.get("query") or ""
    doc_id = _doc_id_from_path(row.get("doc_path") or row.get("doc_id") or "")
    candidates = _parse_list_literal(row.get("documents") or "")
    candidates = [_doc_id_from_path(c) for c in candidates if isinstance(c, str)]
    # Alpha-sort candidates so position-0 is not the gold answer (avoids
    # trivial baseline leakage where stable-sort with zero scores returns
    # the gold for free). Gold-doc identity is preserved; only order changes.
    candidates = sorted(set(candidates))

    pages: List[int] = []
    if subset == "slidevqa":
        pages = [int(p) for p in _parse_list_literal(row.get("evidence_pages", "")) if isinstance(p, int)]
    if not pages:
        pages = [1]  # doc-level fallback

    return {
        "query_id": str(q_id),
        "query": question,
        "gold_doc_ids": [doc_id] if doc_id else [],
        "gold_page_numbers": pages,
        "metadata": {
            "subset": subset,
            "candidate_docs": candidates,
            "answer": row.get("answer", ""),
        },
    }


SUBSET_CSV = {
    "feta_tab": "feta_tab/feta_tab.csv",
    "paper_tab": "paper_tab/paper_tab.csv",
    "scigraphvqa": "scigraphvqa/scigraphqa.csv",
    "slidevqa": "slidevqa/slidevqa.csv",
    "spiqa": "spiqa/spiqa.csv",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--out", default="data/sota_runs/datasets")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    server = cfg["ssh_servers"][0]
    pwd = _resolve_env(server.get("target_password", "")) or os.environ.get("SSH_PRIMARY_PASSWORD", "")
    if not pwd:
        print("SSH_PRIMARY_PASSWORD not set", file=sys.stderr)
        sys.exit(1)

    transport = paramiko.Transport((server["target_host"], server["target_port"]))
    transport.connect(username=server["target_user"], password=pwd)
    sftp = paramiko.SFTPClient.from_transport(transport)

    visdom_remote = server["deployment"]["visdom_data"]
    os.makedirs(args.out, exist_ok=True)

    for subset, rel in SUBSET_CSV.items():
        local_dir = os.path.join(args.out, subset)
        os.makedirs(local_dir, exist_ok=True)
        out_path = os.path.join(local_dir, "queries.jsonl")
        if (os.path.exists(out_path) and os.path.getsize(out_path) > 0
                and not args.force):
            print(f"[skip] {subset} (already cached)")
            continue

        remote = f"{visdom_remote}/{rel}"
        try:
            with sftp.open(remote) as f:
                data = f.read()
        except Exception as e:
            print(f"[miss] {subset}: {e}")
            continue

        text = data.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        rows = [_convert_row(subset, r) for r in reader]
        rows = [r for r in rows if r["query"] and r["gold_doc_ids"]]
        with open(out_path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[ok] {subset}: {len(rows)} queries → {out_path}")

    sftp.close()
    transport.close()


if __name__ == "__main__":
    main()
