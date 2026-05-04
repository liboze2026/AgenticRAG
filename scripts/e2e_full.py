"""End-to-end smoke test for the full backend.

Hits every public endpoint with realistic payloads and prints a one-line
result per check. Designed to surface 500s, hangs, and degraded-but-200
responses (e.g. answer="" but status_code=200).

Run after the backend is up on http://127.0.0.1:8080. Exit code is 0 when
every required check passes; non-zero when at least one fails.
"""
import json
import sys
import time
import traceback
from typing import Any, Optional

import httpx


BASE = "http://127.0.0.1:8080/api"
# trust_env=False bypasses Windows system proxies — when one is configured
# (HTTP_PROXY env or registry setting), httpx routes 127.0.0.1 through it
# and the proxy returns 502 because it can't reach the target host.
client = httpx.Client(base_url=BASE, timeout=180, trust_env=False)

PASS, FAIL, WARN = 0, 0, 0
FAILURES: list = []


def chk(label: str, ok: bool, detail: str = "", warn_only: bool = False):
    global PASS, FAIL, WARN
    if ok:
        PASS += 1
        print(f"  PASS  {label}  {detail}")
    elif warn_only:
        WARN += 1
        print(f"  WARN  {label}  {detail}")
    else:
        FAIL += 1
        FAILURES.append((label, detail))
        print(f"  FAIL  {label}  {detail}")


def hit(method: str, path: str, **kw) -> tuple[Optional[httpx.Response], float, Optional[Exception]]:
    t0 = time.time()
    try:
        r = client.request(method, path, **kw)
        return r, (time.time() - t0) * 1000, None
    except Exception as e:
        return None, (time.time() - t0) * 1000, e


def section(title: str):
    print(f"\n=== {title} ===")


# ---- 1. Health ---------------------------------------------------------
section("1. Health checks")
r, ms, e = hit("GET", "/health")
chk("GET /api/health", r is not None and r.status_code == 200, f"{ms:.0f}ms")
if r and r.status_code == 200:
    j = r.json()
    chk("  worker.status", j.get("worker", {}).get("status") == "ok", str(j.get("worker")))
    chk("  qdrant.status", j.get("qdrant", {}).get("status") == "ok", str(j.get("qdrant")))

r, ms, e = hit("GET", "/lab/health")
chk("GET /api/lab/health", r is not None and r.status_code == 200, f"{ms:.0f}ms")
LAB_HEALTH = r.json() if r and r.status_code == 200 else {}
chk("  main_pipeline_ok", LAB_HEALTH.get("main_pipeline_ok") is True)
chk("  layout_ready", LAB_HEALTH.get("layout_ready") is True)

r, ms, e = hit("GET", "/lab/info")
chk("GET /api/lab/info", r is not None and r.status_code == 200, f"{ms:.0f}ms")
PHASES = []
if r and r.status_code == 200:
    PHASES = r.json().get("phases", [])
chk("  phases count >= 8", len(PHASES) >= 8, f"got {len(PHASES)}")

# ---- 2. Documents -----------------------------------------------------
section("2. Documents")
r, ms, e = hit("GET", "/documents")
chk("GET /api/documents", r is not None and r.status_code == 200, f"{ms:.0f}ms")
DOCS = r.json() if r and r.status_code == 200 else []
chk("  >=1 document", len(DOCS) >= 1, f"{len(DOCS)} docs")
DOC_ID = DOCS[0]["id"] if DOCS else None
DOC_PAGES = DOCS[0]["total_pages"] if DOCS else 0

if DOC_ID:
    r, ms, e = hit("GET", f"/documents/{DOC_ID}")
    chk(f"GET /api/documents/{DOC_ID[:8]}", r is not None and r.status_code == 200, f"{ms:.0f}ms")

    # layout endpoint
    r, ms, e = hit("GET", f"/documents/{DOC_ID}/layout/1")
    chk(f"GET layout/1", r is not None and r.status_code in (200, 404), f"{r.status_code if r else 'ERR'} {ms:.0f}ms",
        warn_only=(r is not None and r.status_code == 404))

# ---- 3. Main query / retrieve -----------------------------------------
section("3. Main pipeline (legacy /query, /retrieve)")
SAMPLE_QUERIES = [
    "What is the main contribution of this paper?",
    "ColPali late interaction matching",
]
for q in SAMPLE_QUERIES:
    r, ms, e = hit("POST", "/retrieve", json={"query": q, "top_k": 3})
    ok = r is not None and r.status_code == 200
    chk(f"POST /retrieve  «{q[:30]}»", ok, f"{r.status_code if r else 'EXC'} {ms:.0f}ms")
    if ok:
        results = r.json().get("results", [])
        chk(f"  results>=1", len(results) >= 1, f"{len(results)} results")

# Just one /query call (heavy: invokes generator)
q = SAMPLE_QUERIES[0]
r, ms, e = hit("POST", "/query", json={"query": q, "top_k": 3})
ok = r is not None and r.status_code == 200
chk(f"POST /query  «{q[:30]}»", ok, f"{r.status_code if r else 'EXC'} {ms:.0f}ms")
if ok:
    j = r.json()
    chk("  answer non-empty", bool((j.get("answer") or "").strip()), f"len={len(j.get('answer','') or '')}")
    chk("  sources>=1", len(j.get("sources", [])) >= 1, f"{len(j.get('sources', []))}")

# ---- 4. Lab Phase 1-5 -------------------------------------------------
section("4. Lab Phase 1-5 regression")
QQ = "What is the main contribution of this paper?"

# Hybrid
r, ms, e = hit("POST", "/lab/hybrid", json={"query": QQ, "top_k": 3, "candidates": 10, "do_generate": False})
ok = r is not None and r.status_code == 200
chk("POST /lab/hybrid", ok, f"{r.status_code if r else 'EXC'} {ms:.0f}ms")
if ok:
    j = r.json()
    chans = {c["channel"]: len(c["results"]) for c in j.get("channels", [])}
    chk("  channels=bm25,colpali,rrf", set(chans.keys()) >= {"bm25", "colpali", "rrf"}, str(chans))

# VISA
r, ms, e = hit("POST", "/lab/visa", json={"query": QQ, "top_k": 3})
ok = r is not None and r.status_code == 200
chk("POST /lab/visa", ok, f"{r.status_code if r else 'EXC'} {ms:.0f}ms")
if ok:
    j = r.json()
    chk("  visa.answer", bool(j.get("answer", "")), f"len={len(j.get('answer','') or '')}")
    chk("  visa.evidence", len(j.get("evidence_regions", [])) >= 1, f"{len(j.get('evidence_regions', []))}")

# GMM
r, ms, e = hit("POST", "/lab/gmm", json={"query": QQ, "top_k": 5, "candidates": 15})
ok = r is not None and r.status_code == 200
chk("POST /lab/gmm", ok, f"{r.status_code if r else 'EXC'} {ms:.0f}ms")
if ok:
    j = r.json()
    chk("  gmm.dynamic_top_k", j.get("dynamic_top_k", 0) >= 1, f"k={j.get('dynamic_top_k')}")

# Region (might be empty if not indexed)
r, ms, e = hit("POST", "/lab/region/query", json={"query": QQ, "top_k": 5})
ok = r is not None and r.status_code in (200, 503)
chk("POST /lab/region/query", ok, f"{r.status_code if r else 'EXC'} {ms:.0f}ms",
    warn_only=(r is not None and r.status_code == 503))

# ---- 5. Lab Phase 6-9 -------------------------------------------------
section("5. Lab Phase 6-9 (new)")

# Graph
r, ms, e = hit("POST", "/lab/graph", json={"query": QQ, "top_k": 3, "include_neighbours": True})
ok = r is not None and r.status_code == 200
chk("POST /lab/graph", ok, f"{r.status_code if r else 'EXC'} {ms:.0f}ms")
if ok:
    j = r.json()
    chk("  graph.seeds>=1", len(j.get("seeds", [])) >= 1)
    chk("  graph.nodes>=1", len(j.get("nodes", [])) >= 1, f"{len(j.get('nodes', []))} nodes")

# Feedback
r, ms, e = hit("POST", "/lab/feedback",
               json={"query": QQ, "top_k": 3, "candidates": 10, "max_rounds": 2, "do_generate": False})
ok = r is not None and r.status_code == 200
chk("POST /lab/feedback (no gen)", ok, f"{r.status_code if r else 'EXC'} {ms:.0f}ms")
if ok:
    j = r.json()
    chk("  feedback.rounds>=1", len(j.get("rounds", [])) >= 1)

r, ms, e = hit("POST", "/lab/feedback",
               json={"query": QQ, "top_k": 3, "candidates": 10, "max_rounds": 2, "do_generate": True})
ok = r is not None and r.status_code == 200
chk("POST /lab/feedback (with gen)", ok, f"{r.status_code if r else 'EXC'} {ms:.0f}ms")

# Unified — flags off then on
r, ms, e = hit("POST", "/lab/unified", json={
    "query": QQ, "top_k": 3, "candidates": 10,
    "use_hybrid": False, "use_gmm": False, "use_feedback": False,
    "use_visa": False, "use_region": False, "use_graph": False,
    "do_generate": False,
})
ok = r is not None and r.status_code == 200
chk("POST /lab/unified (all off)", ok, f"{r.status_code if r else 'EXC'} {ms:.0f}ms")

r, ms, e = hit("POST", "/lab/unified", json={
    "query": QQ, "top_k": 3, "candidates": 10,
    "use_hybrid": True, "use_gmm": True, "use_feedback": True,
    "use_visa": True, "use_region": False, "use_graph": True,
    "do_generate": True,
})
ok = r is not None and r.status_code == 200
chk("POST /lab/unified (full pipe)", ok, f"{r.status_code if r else 'EXC'} {ms:.0f}ms")
if ok:
    j = r.json()
    stages = [s["name"] for s in j.get("stages", [])]
    chk("  unified.stages>=4", len(stages) >= 4, f"stages={stages}")
    bad = [s for s in j.get("stages", []) if not s.get("ok")]
    chk("  unified.no-bad-stages", not bad, f"bad={[(s['name'], s['note'][:40]) for s in bad]}",
        warn_only=bool(bad))

# Benchmark — needs ground truth
if DOC_ID:
    bench_q = [{"query": "ColPali", "relevant_pages": [{"document_id": DOC_ID, "page_number": 1}]}]
    r, ms, e = hit("POST", "/lab/benchmark", json={
        "queries": bench_q, "channels": ["colpali", "bm25"], "top_k": 5, "timeout_per_query_sec": 30,
    })
    ok = r is not None and r.status_code == 200
    chk("POST /lab/benchmark", ok, f"{r.status_code if r else 'EXC'} {ms:.0f}ms")
    if ok:
        j = r.json()
        metrics = {m["channel"]: m for m in j.get("metrics", [])}
        chk("  benchmark.channels", set(metrics.keys()) == {"colpali", "bm25"}, str(list(metrics.keys())))

# ---- 6. Edge cases ----------------------------------------------------
section("6. Error / edge cases")

# empty query → 400
r, ms, e = hit("POST", "/query", json={"query": "  ", "top_k": 3})
chk("POST /query (empty) → 400", r is not None and r.status_code == 400, f"{r.status_code if r else 'EXC'}")

r, ms, e = hit("POST", "/lab/visa", json={"query": "", "top_k": 3})
chk("POST /lab/visa (empty) → 400", r is not None and r.status_code == 400, f"{r.status_code if r else 'EXC'}")

r, ms, e = hit("POST", "/lab/graph", json={"query": "  ", "top_k": 3})
chk("POST /lab/graph (empty) → 400", r is not None and r.status_code == 400, f"{r.status_code if r else 'EXC'}")

# bad doc id in layout
r, ms, e = hit("GET", "/documents/nonexistent_doc/layout/1")
chk("GET layout (bad doc) → 404", r is not None and r.status_code == 404, f"{r.status_code if r else 'EXC'}")

# benchmark empty
r, ms, e = hit("POST", "/lab/benchmark", json={"queries": [], "channels": ["colpali"], "top_k": 5})
chk("POST /lab/benchmark (empty) → 400", r is not None and r.status_code == 400, f"{r.status_code if r else 'EXC'}")

# benchmark bad channel
r, ms, e = hit("POST", "/lab/benchmark",
               json={"queries": [{"query": "x", "relevant_pages": []}], "channels": ["foobar"], "top_k": 5})
ok = r is not None and r.status_code == 200
chk("POST /lab/benchmark (bad chan) → 200+note", ok, f"{r.status_code if r else 'EXC'}")
if ok:
    j = r.json()
    chk("  notes mentions unsupported", "不支持" in j.get("note", ""), j.get("note", ""))

# unified all flags off — just generate=False
r, ms, e = hit("POST", "/lab/unified", json={
    "query": QQ, "top_k": 3, "candidates": 10,
    "use_hybrid": False, "use_gmm": False, "use_feedback": False,
    "use_visa": False, "use_region": False, "use_graph": False,
    "do_generate": False,
})
ok = r is not None and r.status_code == 200
chk("POST /lab/unified (all-off, no-gen)", ok, f"{r.status_code if r else 'EXC'} {ms:.0f}ms")

# ---- Summary ---------------------------------------------------------
print(f"\n=== Summary: {PASS} passed / {WARN} warn / {FAIL} failed ===")
for label, detail in FAILURES:
    print(f"  - {label}: {detail}")
sys.exit(0 if FAIL == 0 else 1)
