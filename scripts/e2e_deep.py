"""Deep E2E: chat, concurrency, region indexing loop, untested APIs,
citation correctness, edge cases on Phase 6-9.
"""
import asyncio
import json
import sys
import time
from typing import Optional

import httpx


BASE = "http://127.0.0.1:8080/api"
client = httpx.Client(base_url=BASE, timeout=300, trust_env=False)


def _new_aclient():
    """Build a fresh AsyncClient per asyncio.run() — reusing a module-level
    client across multiple asyncio.run() calls binds its transport to the
    previous (now-closed) event loop and the next call returns immediately."""
    return httpx.AsyncClient(base_url=BASE, timeout=300, trust_env=False)

PASS = FAIL = WARN = 0
FAILS: list = []


def chk(label, ok, detail="", warn=False):
    global PASS, FAIL, WARN
    if ok:
        PASS += 1
        print(f"  PASS  {label}  {detail}")
    elif warn:
        WARN += 1
        print(f"  WARN  {label}  {detail}")
    else:
        FAIL += 1
        FAILS.append((label, detail))
        print(f"  FAIL  {label}  {detail}")


def hit(method, path, **kw):
    t0 = time.time()
    try:
        r = client.request(method, path, **kw)
        return r, (time.time() - t0) * 1000
    except Exception as e:
        return e, (time.time() - t0) * 1000


def section(title):
    print(f"\n=== {title} ===")


# Bootstrap: get docs
docs = client.get("/documents").json()
DOC_ID = docs[0]["id"]
DOC_PAGES = docs[0]["total_pages"]
print(f"Using DOC_ID={DOC_ID} ({DOC_PAGES} pages)")


# ---- 1. Chat (multi-turn) --------------------------------------------
section("1. Chat — multi-turn session")
# Turn 1: kicks off a session implicitly (server creates one when session_id is null)
turn1_messages = [{"role": "user", "content": "What is the contribution of this paper?"}]
r, ms = hit("POST", "/chat", json={
    "messages": turn1_messages, "document_ids": [DOC_ID], "top_k": 3,
})
chk("chat turn 1 (POST /chat)", isinstance(r, httpx.Response) and r.status_code == 200,
    f"{r.status_code if isinstance(r, httpx.Response) else 'EXC'} {ms:.0f}ms")
SESSION_ID = None
if isinstance(r, httpx.Response) and r.status_code == 200:
    j = r.json()
    SESSION_ID = j.get("session_id")
    chk("  session_id created", bool(SESSION_ID), SESSION_ID or "")
    chk("  reply non-empty", bool((j.get("message", {}) or {}).get("content")),
        f"len={len(((j.get('message') or {}).get('content') or ''))}")

# Turn 2: same session, append assistant reply + new user turn
if SESSION_ID:
    turn2_messages = list(turn1_messages) + [
        {"role": "assistant", "content": (r.json().get("message") or {}).get("content", "")},
        {"role": "user", "content": "Can you elaborate on that?"},
    ]
    r, ms = hit("POST", "/chat", json={
        "messages": turn2_messages, "document_ids": [DOC_ID],
        "session_id": SESSION_ID, "top_k": 3,
    })
    chk("chat turn 2 (same session)", isinstance(r, httpx.Response) and r.status_code == 200,
        f"{r.status_code if isinstance(r, httpx.Response) else 'EXC'} {ms:.0f}ms")
    if isinstance(r, httpx.Response) and r.status_code == 200:
        chk("  turn2 same session", r.json().get("session_id") == SESSION_ID,
            f"got {r.json().get('session_id')}")

    # Get session
    r, ms = hit("GET", f"/chat/sessions/{SESSION_ID}")
    chk("GET session", isinstance(r, httpx.Response) and r.status_code == 200, f"{ms:.0f}ms")
    if isinstance(r, httpx.Response) and r.status_code == 200:
        msgs = r.json().get("messages", [])
        chk("  >=4 messages persisted", len(msgs) >= 4, f"got {len(msgs)}")

    # Cleanup: delete session
    r, ms = hit("DELETE", f"/chat/sessions/{SESSION_ID}")
    chk("DELETE session", isinstance(r, httpx.Response) and r.status_code == 200, f"{ms:.0f}ms")


# ---- 2. Chinese / long / special-char queries ------------------------
section("2. Query variants (Chinese / long / special chars)")
test_queries = [
    ("Chinese", "这篇论文的主要贡献是什么？"),
    ("CJK + en", "ColPali 的 late interaction 机制如何工作？"),
    ("Long", "Please provide a comprehensive overview of the methodology, experimental setup, results, ablation studies, and limitations discussed in this paper, focusing especially on the multi-vector embedding approach and the late-interaction matching scheme."),
    ("Special chars", "What is α-β optimization? (e.g., loss = ||y - Wx||² + λ‖W‖)"),
    ("Numbers", "What is the model size in Table 1?"),
]
for tag, q in test_queries:
    r, ms = hit("POST", "/retrieve", json={"query": q, "top_k": 3})
    chk(f"retrieve [{tag}]", isinstance(r, httpx.Response) and r.status_code == 200,
        f"{r.status_code if isinstance(r, httpx.Response) else 'EXC'} {ms:.0f}ms")


# ---- 3. Concurrency / health flood -----------------------------------
section("3. Concurrency stress")

async def flood_health(c):
    return await asyncio.gather(*[c.get("/health") for _ in range(10)], return_exceptions=True)


async def flood_retrieve(c):
    return await asyncio.gather(
        *[c.post("/retrieve", json={"query": f"test query {i}", "top_k": 3}) for i in range(5)],
        return_exceptions=True,
    )


async def run_concurrency():
    async with _new_aclient() as c:
        t0 = time.time()
        h = await flood_health(c)
        dt_h = (time.time() - t0) * 1000
        t0 = time.time()
        r = await flood_retrieve(c)
        dt_r = (time.time() - t0) * 1000
    return h, dt_h, r, dt_r


h_results, dt_h, r_results, dt_r = asyncio.run(run_concurrency())
ok_h = sum(1 for r in h_results if isinstance(r, httpx.Response) and r.status_code == 200)
chk("10 parallel /health", ok_h == 10, f"{ok_h}/10 ok in {dt_h:.0f}ms")
ok_r = sum(1 for r in r_results if isinstance(r, httpx.Response) and r.status_code == 200)
bad_detail = next(
    (f"{type(r).__name__}: {r}" for r in r_results
     if not (isinstance(r, httpx.Response) and r.status_code == 200)),
    "",
)
chk("5 parallel /retrieve", ok_r == 5, f"{ok_r}/5 ok in {dt_r:.0f}ms" + (f"  err={bad_detail[:80]}" if bad_detail else ""))


# ---- 4. VISA citation correctness ------------------------------------
section("4. VISA citation correctness")
r, ms = hit("POST", "/lab/visa", json={"query": "What is the main contribution?", "top_k": 3})
if isinstance(r, httpx.Response) and r.status_code == 200:
    j = r.json()
    answer = j.get("answer", "")
    sources = j.get("sources", [])
    regions = j.get("evidence_regions", [])
    import re
    cites = [int(m) for m in re.findall(r"\[(\d+)\]", answer)]
    chk("visa answer has citations", len(cites) > 0, f"{len(cites)} citation markers")
    chk("visa cite indices in range", all(1 <= c <= len(sources) for c in cites),
        f"cites={cites} sources={len(sources)}")
    chk("visa regions point to valid sources",
        all(1 <= e["citation"] <= len(sources) for e in regions),
        f"regions citations={[e['citation'] for e in regions]}")
    chk("visa region count >= unique citations",
        len(regions) >= len(set(cites)),
        f"regions={len(regions)} unique_cites={len(set(cites))}")
else:
    chk("visa request OK", False, str(r))


# ---- 5. Layout API edges ---------------------------------------------
section("5. Layout API edges")
r, ms = hit("GET", f"/documents/{DOC_ID}/layout/0")  # page=0
chk("layout page=0 → 4xx", isinstance(r, httpx.Response) and r.status_code in (404, 422), str(r.status_code if isinstance(r, httpx.Response) else r))
r, ms = hit("GET", f"/documents/{DOC_ID}/layout/{DOC_PAGES + 100}")
chk("layout page>>total → 4xx", isinstance(r, httpx.Response) and r.status_code in (404, 422), str(r.status_code if isinstance(r, httpx.Response) else r))
r, ms = hit("GET", f"/documents/{DOC_ID}/layout/{DOC_PAGES}")  # last page
chk("layout last page → 200/404", isinstance(r, httpx.Response) and r.status_code in (200, 404),
    str(r.status_code if isinstance(r, httpx.Response) else r))


# ---- 6. Region: index → query loop -----------------------------------
section("6. Region indexing loop")
r, ms = hit("GET", f"/lab/region/status/{DOC_ID}")
chk("region status", isinstance(r, httpx.Response) and r.status_code == 200, f"{ms:.0f}ms")
if isinstance(r, httpx.Response) and r.status_code == 200:
    state = r.json().get("state")
    chk("  state field", state in ("not_started", "completed", "running", "pending"), str(state))

r, ms = hit("GET", "/lab/region/jobs")
chk("region jobs", isinstance(r, httpx.Response) and r.status_code == 200, f"{ms:.0f}ms")


# ---- 7. Other APIs (system, datasets, experiments, cache, visdom) -----
section("7. Other APIs")
for path in [
    "/system",
    "/datasets",
    "/experiments",
    "/cache/stats",
]:
    r, ms = hit("GET", path)
    chk(f"GET {path}", isinstance(r, httpx.Response) and r.status_code in (200, 404),
        f"{r.status_code if isinstance(r, httpx.Response) else 'EXC'} {ms:.0f}ms",
        warn=(isinstance(r, httpx.Response) and r.status_code == 404))


# ---- 8. Phase 6-9 deeper ---------------------------------------------
section("8. Phase 6-9 deeper")

# Graph w/o neighbours
r, ms = hit("POST", "/lab/graph", json={"query": "ColPali", "top_k": 2, "include_neighbours": False})
chk("graph no-neighbours", isinstance(r, httpx.Response) and r.status_code == 200,
    f"{r.status_code if isinstance(r, httpx.Response) else 'EXC'} {ms:.0f}ms")

# Feedback with very small candidates → triggers low-density
r, ms = hit("POST", "/lab/feedback",
            json={"query": "Some unusual query that may not match", "top_k": 3, "candidates": 6, "max_rounds": 2, "do_generate": False})
chk("feedback small candidate set", isinstance(r, httpx.Response) and r.status_code == 200,
    f"{r.status_code if isinstance(r, httpx.Response) else 'EXC'} {ms:.0f}ms")
if isinstance(r, httpx.Response) and r.status_code == 200:
    j = r.json()
    chk("  feedback returned rounds", len(j.get("rounds", [])) >= 1, f"{len(j.get('rounds', []))}")

# Unified with only_region (region depends on collection)
r, ms = hit("POST", "/lab/unified", json={
    "query": "ColPali", "top_k": 3, "candidates": 10,
    "use_hybrid": False, "use_gmm": False, "use_feedback": False,
    "use_visa": False, "use_region": True, "use_graph": False,
    "do_generate": False,
})
chk("unified region-only", isinstance(r, httpx.Response) and r.status_code == 200,
    f"{r.status_code if isinstance(r, httpx.Response) else 'EXC'} {ms:.0f}ms")

# Benchmark with multiple queries
r, ms = hit("POST", "/lab/benchmark", json={
    "queries": [
        {"query": "main contribution", "relevant_pages": [{"document_id": DOC_ID, "page_number": 1}]},
        {"query": "experiments", "relevant_pages": [{"document_id": DOC_ID, "page_number": 5}]},
        {"query": "conclusion", "relevant_pages": [{"document_id": DOC_ID, "page_number": DOC_PAGES}]},
    ],
    "channels": ["colpali", "bm25", "rrf"],
    "top_k": 5, "timeout_per_query_sec": 30,
})
chk("benchmark 3q × 3ch", isinstance(r, httpx.Response) and r.status_code == 200,
    f"{r.status_code if isinstance(r, httpx.Response) else 'EXC'} {ms:.0f}ms")
if isinstance(r, httpx.Response) and r.status_code == 200:
    j = r.json()
    chk("  benchmark per_query=9", len(j.get("per_query", [])) == 9, f"{len(j.get('per_query', []))}")
    chk("  benchmark metrics=3", len(j.get("metrics", [])) == 3, f"{len(j.get('metrics', []))}")


# ---- 9. Boundary inputs ---------------------------------------------
section("9. Boundary inputs")

# Very long query
long_q = "ColPali " * 500   # ~4000 chars
r, ms = hit("POST", "/lab/visa", json={"query": long_q, "top_k": 3})
chk("visa long-query (4000+) → 400 or handle", isinstance(r, httpx.Response) and r.status_code in (200, 400),
    f"{r.status_code if isinstance(r, httpx.Response) else 'EXC'}")

# top_k out of bounds
r, ms = hit("POST", "/lab/visa", json={"query": "ok", "top_k": 999})
chk("visa top_k=999 → 422", isinstance(r, httpx.Response) and r.status_code == 422,
    f"{r.status_code if isinstance(r, httpx.Response) else 'EXC'}")

# Negative top_k
r, ms = hit("POST", "/lab/gmm", json={"query": "ok", "top_k": -1})
chk("gmm top_k=-1 → 422", isinstance(r, httpx.Response) and r.status_code == 422,
    f"{r.status_code if isinstance(r, httpx.Response) else 'EXC'}")

# Benchmark too many
big_queries = [{"query": f"q{i}", "relevant_pages": []} for i in range(250)]
r, ms = hit("POST", "/lab/benchmark", json={"queries": big_queries, "channels": ["bm25"], "top_k": 5})
chk("benchmark 250q → 400", isinstance(r, httpx.Response) and r.status_code == 400,
    f"{r.status_code if isinstance(r, httpx.Response) else 'EXC'}")


# ---- Summary ---------------------------------------------------------
print(f"\n=== Summary: {PASS} passed / {WARN} warn / {FAIL} failed ===")
for label, detail in FAILS:
    print(f"  - {label}: {detail}")
sys.exit(0 if FAIL == 0 else 1)
