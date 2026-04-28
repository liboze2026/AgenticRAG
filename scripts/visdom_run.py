"""
VisDoM SPIQA mini-reproduction (sequential & robust):
1. Reset: delete any prior VisDoM docs from the backend
2. For each of the 5 PDFs: upload, then wait for completion before next upload
3. Run all queries via /api/retrieve, compute doc-level Recall@K + MRR
4. Persist results JSON (and mirror to frontend/public/visdom/)
"""
import io
import json
import os
import sys
import time
import requests

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(PROJECT, "data", "visdom_spiqa_mini")
PDF_DIR = os.path.join(DATA, "pdfs")

API = "http://localhost:8080/api"
KS = (1, 3, 5, 10)


def health():
    return requests.get(f"{API}/health", timeout=60).json()


def list_docs():
    return requests.get(f"{API}/documents", timeout=30).json()


def delete_doc(doc_id: str):
    requests.delete(f"{API}/documents/{doc_id}", timeout=60)


def upload(pdf_path: str) -> str:
    with open(pdf_path, "rb") as f:
        files = {"file": (os.path.basename(pdf_path), f, "application/pdf")}
        r = requests.post(f"{API}/documents/upload", files=files, timeout=120)
        r.raise_for_status()
        return r.json()["id"]


def get_doc(doc_id: str):
    docs = list_docs()
    for d in docs:
        if d["id"] == doc_id:
            return d
    return None


def wait_one(doc_id: str, timeout_s: int = 1500) -> dict:
    """Wait until doc is completed or failed."""
    deadline = time.time() + timeout_s
    last_print = 0
    while time.time() < deadline:
        d = get_doc(doc_id)
        if d is None:
            time.sleep(2)
            continue
        if d["status"] in ("completed", "failed"):
            return d
        now = time.time()
        if now - last_print > 12:
            print(f"    ...{d['status']} {d['indexed_pages']}/{d['total_pages']}")
            last_print = now
        time.sleep(4)
    raise RuntimeError(f"Indexing timeout for {doc_id}")


def retrieve(query: str, top_k: int = 10) -> dict:
    r = requests.post(f"{API}/retrieve", json={"query": query, "top_k": top_k}, timeout=180)
    r.raise_for_status()
    return r.json()


def main():
    print("--- 0. Health ---")
    h = health()
    if h.get("status") != "ok":
        print(f"  unhealthy: {h}")
        sys.exit(1)
    print(f"  ok  worker={h['worker'].get('model','?')}  qdrant={h['qdrant'].get('status','?')}\n")

    eval_path = os.path.join(DATA, "eval.json")
    with open(eval_path, encoding="utf-8") as f:
        queries = json.load(f)
    target_docs = sorted({q["target_doc"] for q in queries})
    print(f"target papers: {target_docs}\n")

    print("--- 1. Cleanup any prior VisDoM docs ---")
    target_filenames = {f"{a}.pdf" for a in target_docs}
    for d in list_docs():
        if d["filename"] in target_filenames:
            print(f"  delete prior {d['id'][:8]}  status={d['status']}  ({d['filename']})")
            delete_doc(d["id"])
    time.sleep(2)
    print()

    print("--- 2. Upload + wait per doc (sequential) ---")
    arxiv_to_id = {}
    for arxiv in target_docs:
        fname = f"{arxiv}.pdf"
        pdf = os.path.join(PDF_DIR, fname)
        print(f"  [{arxiv}]")
        print(f"    upload ...", end="", flush=True)
        doc_id = upload(pdf)
        print(f" -> {doc_id[:8]}")
        d = wait_one(doc_id, timeout_s=1500)
        print(f"    final: status={d['status']} pages={d['indexed_pages']}/{d['total_pages']}")
        if d["status"] != "completed":
            raise RuntimeError(f"{arxiv} did not complete")
        arxiv_to_id[arxiv] = doc_id
    print()

    indexed_pages = {arxiv_to_id[a]: get_doc(arxiv_to_id[a])["indexed_pages"] for a in target_docs}

    print("--- 3. Run queries ---")
    per_query_results = []
    sum_rr = 0.0
    recall_hit = {k: 0 for k in KS}
    sum_timing = {}
    for i, q in enumerate(queries):
        target_id = arxiv_to_id[q["target_doc"]]
        try:
            resp = retrieve(q["query"], top_k=10)
        except Exception as e:
            print(f"  [{i+1}/{len(queries)}] FAIL: {e}")
            continue
        retrieved = resp.get("results", [])
        retrieved_doc_ids = [r["document_id"] for r in retrieved]
        seen = set()
        retrieved_unique = []
        for d in retrieved_doc_ids:
            if d not in seen:
                seen.add(d)
                retrieved_unique.append(d)
        rec_per_k = {}
        for k in KS:
            hit = target_id in retrieved_unique[:k]
            rec_per_k[k] = 1.0 if hit else 0.0
            if hit:
                recall_hit[k] += 1
        rr = 0.0
        for rank, d in enumerate(retrieved_unique, start=1):
            if d == target_id:
                rr = 1.0 / rank
                break
        sum_rr += rr
        for k, v in (resp.get("timing") or {}).items():
            sum_timing[k] = sum_timing.get(k, 0.0) + v
        per_query_results.append({
            "q_id": q["q_id"],
            "query": q["query"],
            "target_doc": q["target_doc"],
            "target_doc_id_local": target_id,
            "retrieved_unique_ordered": retrieved_unique,
            "retrieved_pages": [{"doc_id": r["document_id"], "page": r["page_number"], "score": r["score"]} for r in retrieved[:10]],
            "rr": rr,
            "recall_at_k": rec_per_k,
            "timing_ms": resp.get("timing", {}),
        })
        if (i + 1) % 5 == 0 or (i + 1) == len(queries):
            n_so_far = i + 1
            print(f"  [{n_so_far}/{len(queries)}]  R@1={recall_hit[1]/n_so_far:.3f}  R@5={recall_hit[5]/n_so_far:.3f}  MRR={sum_rr/n_so_far:.4f}")

    n = len(per_query_results)
    avg_recall = {f"recall@{k}": recall_hit[k] / n for k in KS}
    avg_mrr = sum_rr / n
    avg_timing = {k: v / n for k, v in sum_timing.items()}
    print(f"\n=== AGGREGATE ({n} queries) ===")
    for k in KS:
        print(f"  recall@{k}: {avg_recall[f'recall@{k}']:.4f}")
    print(f"  MRR:       {avg_mrr:.4f}")
    print(f"  avg timing: {avg_timing}")

    with open(os.path.join(DATA, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    result = {
        "manifest": manifest,
        "target_doc_id_map": arxiv_to_id,
        "indexed_pages": indexed_pages,
        "metrics": {
            **avg_recall,
            "mrr": avg_mrr,
            "n_queries": n,
            "avg_timing_ms": avg_timing,
        },
        "per_query": per_query_results,
    }
    out = os.path.join(DATA, "results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n[+] Results saved: {out}")

    fe_dir = os.path.join(PROJECT, "frontend", "public", "visdom")
    os.makedirs(fe_dir, exist_ok=True)
    fe_out = os.path.join(fe_dir, "results.json")
    with open(fe_out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[+] Mirrored to frontend: {fe_out}")


if __name__ == "__main__":
    main()
