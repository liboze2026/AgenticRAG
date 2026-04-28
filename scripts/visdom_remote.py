"""
VisDoM SPIQA mini-reproduction — runs ENTIRELY on the remote GPU server.
Uses worker localhost:8001 directly. No Qdrant. Computes MaxSim in-memory.
Outputs:
  /tmp/visdom_out/results.json
  /tmp/visdom_out/pages/<arxiv>/page_<n>.png
Pull these back via sftp afterwards.
"""
import os, sys, json, csv, base64, time, collections, glob, shutil
import requests
from pdf2image import convert_from_path

DATA_ROOT = "/home/bzli/lbz/data/VisDoM-main/spiqa"
OUT = "/tmp/visdom_out"
PAGES_DIR = f"{OUT}/pages"
WORKER = "http://localhost:8001"
TOP_N = 3
MAX_QUERIES = 60
KS = (1, 3, 5, 10)

os.makedirs(PAGES_DIR, exist_ok=True)

# 1. pick top-N papers ----------------------------------------------------
with open(f"{DATA_ROOT}/spiqa.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
ctr = collections.Counter(r["doc_id"] for r in rows)
top = [doc for doc, _ in ctr.most_common(TOP_N)]
print(f"papers: {top}", flush=True)
selected = [r for r in rows if r["doc_id"] in top][:MAX_QUERIES]
print(f"queries: {len(selected)}", flush=True)

# 2. render pages for each paper -----------------------------------------
doc_pages = {}    # arxiv -> list of (page_number, file_path)
doc_pagecount = {}
for arxiv in top:
    pdf = f"{DATA_ROOT}/docs/{arxiv}.pdf"
    out_dir = f"{PAGES_DIR}/{arxiv}"
    os.makedirs(out_dir, exist_ok=True)
    if len(glob.glob(f"{out_dir}/page_*.png")) > 0:
        # already rendered
        files = sorted(glob.glob(f"{out_dir}/page_*.png"))
        print(f"  [{arxiv}] cached {len(files)} pages", flush=True)
    else:
        print(f"  [{arxiv}] rendering ...", end="", flush=True)
        t0 = time.time()
        images = convert_from_path(pdf, dpi=150)
        for i, img in enumerate(images, start=1):
            img.save(f"{out_dir}/page_{i}.png", "PNG")
        files = sorted(glob.glob(f"{out_dir}/page_*.png"))
        print(f" {len(files)} pages in {time.time()-t0:.1f}s", flush=True)
    pages = []
    for f in files:
        n = int(os.path.basename(f).split("_")[1].split(".")[0])
        pages.append((n, f))
    pages.sort(key=lambda x: x[0])
    doc_pages[arxiv] = pages
    doc_pagecount[arxiv] = len(pages)

# 3. encode all pages with worker ----------------------------------------
print("encoding documents ...", flush=True)
doc_embeddings = {}    # arxiv -> list of (page_number, vectors:list[list[float]])
batch = 4
for arxiv, pages in doc_pages.items():
    embs = []
    for i in range(0, len(pages), batch):
        chunk = pages[i:i+batch]
        b64s = []
        for _, fp in chunk:
            with open(fp, "rb") as f:
                b64s.append(base64.b64encode(f.read()).decode())
        t0 = time.time()
        r = requests.post(f"{WORKER}/encode/documents", json={"images_b64": b64s}, timeout=600)
        r.raise_for_status()
        out = r.json()["embeddings"]
        for (page_num, _), e in zip(chunk, out):
            embs.append((page_num, e["vectors"]))
        print(f"  [{arxiv}] batch {i//batch+1} ({len(chunk)} pages) in {time.time()-t0:.1f}s", flush=True)
    doc_embeddings[arxiv] = embs

# 4. run queries ----------------------------------------------------------
print("encoding queries + retrieving ...", flush=True)
def maxsim(query_vecs, doc_vecs):
    """MaxSim score: sum over each query token of max similarity to any doc patch."""
    score = 0.0
    for qv in query_vecs:
        best = -1e9
        for dv in doc_vecs:
            s = 0.0
            for a, b in zip(qv, dv):
                s += a * b
            if s > best:
                best = s
        score += best
    return score

# flatten (arxiv, page, vectors) tuples
all_pages_idx = []
for arxiv, embs in doc_embeddings.items():
    for page_num, vecs in embs:
        all_pages_idx.append((arxiv, page_num, vecs))

per_query = []
recall_hit = {k: 0 for k in KS}
sum_rr = 0.0
sum_q_enc_ms = 0.0
sum_score_ms = 0.0
for qi, q in enumerate(selected):
    target = q["doc_id"]
    t0 = time.time()
    r = requests.post(f"{WORKER}/encode/query", json={"query": q["question"]}, timeout=120)
    r.raise_for_status()
    qvecs = r.json()["vectors"]
    q_enc_ms = (time.time() - t0) * 1000
    sum_q_enc_ms += q_enc_ms

    t0 = time.time()
    scored = []
    for arxiv, page_num, vecs in all_pages_idx:
        s = maxsim(qvecs, vecs)
        scored.append((s, arxiv, page_num))
    scored.sort(reverse=True)
    score_ms = (time.time() - t0) * 1000
    sum_score_ms += score_ms

    # doc-level dedupe order
    seen = set()
    retrieved_unique = []
    for s, arxiv, p in scored:
        if arxiv not in seen:
            seen.add(arxiv)
            retrieved_unique.append(arxiv)
    rec_per_k = {k: 1.0 if target in retrieved_unique[:k] else 0.0 for k in KS}
    for k, v in rec_per_k.items():
        if v > 0:
            recall_hit[k] += 1
    rr = 0.0
    for rank, arxiv in enumerate(retrieved_unique, start=1):
        if arxiv == target:
            rr = 1.0 / rank
            break
    sum_rr += rr

    per_query.append({
        "q_id": q["q_id"],
        "query": q["question"],
        "target_doc": target,
        "reference_figure": q["reference_figure"],
        "paper_title": q["paper_title"],
        "retrieved_unique_ordered": retrieved_unique,
        "retrieved_pages": [
            {"doc_id": arxiv, "page": p, "score": s}
            for s, arxiv, p in scored[:10]
        ],
        "rr": rr,
        "recall_at_k": rec_per_k,
        "timing_ms": {"query_encode_ms": q_enc_ms, "score_ms": score_ms, "total_ms": q_enc_ms + score_ms},
    })
    if (qi+1) % 5 == 0 or (qi+1) == len(selected):
        n = qi + 1
        print(f"  [{n}/{len(selected)}] R@1={recall_hit[1]/n:.3f} R@5={recall_hit[5]/n:.3f} MRR={sum_rr/n:.4f}", flush=True)

n = len(per_query)
metrics = {
    **{f"recall@{k}": recall_hit[k] / n for k in KS},
    "mrr": sum_rr / n,
    "n_queries": n,
    "avg_timing_ms": {
        "query_encode_ms": sum_q_enc_ms / n,
        "score_ms": sum_score_ms / n,
        "total_ms": (sum_q_enc_ms + sum_score_ms) / n,
    },
}
print(f"\n=== FINAL ===", flush=True)
for k in KS:
    print(f"  recall@{k}: {metrics[f'recall@{k}']:.4f}", flush=True)
print(f"  MRR:       {metrics['mrr']:.4f}", flush=True)

manifest = {
    "dataset": "VisDoM/SPIQA",
    "subset_strategy": f"按查询数排序取前 {TOP_N} 篇论文",
    "papers": top,
    "doc_pages": doc_pagecount,
    "queries_in_eval": len(per_query),
    "queries_total_in_subset": len([r for r in rows if r["doc_id"] in top]),
    "csv_source": f"{DATA_ROOT}/spiqa.csv",
    "pdf_source": f"{DATA_ROOT}/docs",
}
result = {
    "manifest": manifest,
    "papers_meta": {
        arxiv: {"pages": doc_pagecount[arxiv]}
        for arxiv in top
    },
    "metrics": metrics,
    "per_query": per_query,
}
with open(f"{OUT}/results.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"saved {OUT}/results.json", flush=True)
