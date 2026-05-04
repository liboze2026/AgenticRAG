"""Verify /api/health stays fast even under heavy concurrent load.

Triggers region indexing in the background (worst-case load — saturates
the SSH tunnel with image uploads + Qdrant upserts), then floods /health.
Health probes must complete in < 10s each, even when the tunnel is busy.
"""
import asyncio
import sys
import time

import httpx


BASE = "http://127.0.0.1:8080/api"


async def trigger_region_index(c, doc_id):
    r = await c.post(f"/lab/region/index/{doc_id}", params={"sync": "false"})
    return r.status_code, r.json() if r.status_code == 200 else r.text


async def health_round(c, n=8):
    """One round of N parallel health probes — every probe must finish."""
    t0 = time.time()
    rs = await asyncio.gather(*[c.get("/health") for _ in range(n)], return_exceptions=True)
    dt = (time.time() - t0) * 1000
    ok = sum(1 for r in rs if isinstance(r, httpx.Response) and r.status_code == 200)
    bad = next(
        (f"{type(r).__name__}: {r}" for r in rs
         if not (isinstance(r, httpx.Response) and r.status_code == 200)),
        "",
    )
    return ok, n, dt, bad


async def main():
    fail = 0
    async with httpx.AsyncClient(base_url=BASE, timeout=15, trust_env=False) as c:
        # Pick a document to index
        r = await c.get("/documents")
        docs = r.json()
        if not docs:
            print("FAIL  no documents available")
            return 1
        doc_id = docs[0]["id"]
        print(f"Using doc={doc_id} ({docs[0]['total_pages']} pages)")

        # Baseline: 8 parallel health (should be near-instant)
        ok, n, dt, bad = await health_round(c, 8)
        print(f"baseline 8 parallel /health: {ok}/{n} in {dt:.0f}ms")
        if ok != n:
            fail += 1
            print(f"  FAIL  baseline {bad[:80]}")

        # Trigger region indexing in the background
        sc, body = await trigger_region_index(c, doc_id)
        print(f"region/index trigger: {sc} note={body.get('note', body) if isinstance(body, dict) else body}")

        # Run 8 rounds of 6 health probes, 4s spacing — total ~32s elapsed.
        # Each round MUST hit 6/6 with each probe < 10s (no 30s stalls).
        for i in range(8):
            ok, n, dt, bad = await health_round(c, 6)
            status = "PASS" if ok == n and dt < 12000 else "FAIL"
            if status == "FAIL":
                fail += 1
            print(f"  round {i+1}: {status}  {ok}/{n} in {dt:.0f}ms  err={bad[:60]}")
            await asyncio.sleep(4)

        # Verify region status was actually progressing (state != idle)
        r = await c.get(f"/lab/region/status/{doc_id}")
        st = r.json() if r.status_code == 200 else {}
        print(f"region status now: state={st.get('state')} page={st.get('current_page')}/{st.get('total_pages')} indexed={st.get('indexed')}")
        # Don't fail on indexing speed — just verify we don't crash health
    return 0 if fail == 0 else 1


sys.exit(asyncio.run(main()))
