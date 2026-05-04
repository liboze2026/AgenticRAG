"""Deep QA — inspect response payloads, not just status codes."""
import asyncio, io, json, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
for _v in ("NO_PROXY","no_proxy"): os.environ[_v]=(os.environ.get(_v,"")+",localhost,127.0.0.1").lstrip(",")
for _v in ("HTTP_PROXY","HTTPS_PROXY","http_proxy","https_proxy"): os.environ[_v]=""
import httpx

BASE = "http://127.0.0.1:8080"
Q = "什么是 ColPali 的 late interaction 机制?"


def banner(s): print(f"\n{'='*60}\n{s}\n{'='*60}")


async def main():
    issues = []
    async with httpx.AsyncClient(trust_env=False, timeout=180) as c:
        # ---- Health
        banner("[1] Lab Health")
        r = await c.get(f"{BASE}/api/lab/health"); h = r.json()
        print(json.dumps(h, indent=2, ensure_ascii=False))
        if not h["main_pipeline_ok"]: issues.append("main pipeline not ok")
        if not h["layout_ready"]: issues.append("no docs with layout")

        # ---- Documents
        banner("[2] Documents")
        docs = (await c.get(f"{BASE}/api/documents")).json()
        for d in docs: print(f"  {d['id']:8s} | {d['filename']:40s} | {d['status']:10s} | {d['indexed_pages']}p")
        completed = [d for d in docs if d["status"]=="completed"]
        if not completed: issues.append("no completed docs"); return issues

        # ---- /api/query (full pipeline w/ generation)
        banner("[3] /api/query")
        r = await c.post(f"{BASE}/api/query", json={"query": Q, "top_k": 3})
        if r.status_code != 200:
            issues.append(f"/api/query status={r.status_code} {r.text[:200]}")
        else:
            qq = r.json()
            print(f"  answer len: {len(qq['answer'])}")
            print(f"  sources: {len(qq['sources'])}")
            print(f"  timing: {qq.get('timing')}")
            if not qq['answer']: issues.append("/api/query empty answer")
            if not qq['sources']: issues.append("/api/query no sources")

        # ---- Hybrid
        banner("[4] /api/lab/hybrid")
        r = await c.post(f"{BASE}/api/lab/hybrid",
            json={"query": Q, "top_k": 3, "candidates": 15, "do_generate": False})
        if r.status_code != 200:
            issues.append(f"/api/lab/hybrid {r.status_code}")
        else:
            h = r.json()
            for ch in h["channels"]:
                print(f"  [{ch['channel']:8s}] {len(ch['results'])} results, {ch['timing_ms']:.0f}ms — {ch['note'][:80]}")
            bm25 = next((c for c in h["channels"] if c["channel"]=="bm25"), None)
            if bm25 and len(bm25["results"]) == 0 and "为空" not in (bm25["note"] or ""):
                issues.append("hybrid: BM25 empty without note")
            if not any(c["channel"]=="rrf" for c in h["channels"]):
                issues.append("hybrid: missing RRF channel")

        # ---- VISA
        banner("[5] /api/lab/visa")
        r = await c.post(f"{BASE}/api/lab/visa", json={"query": Q, "top_k": 3})
        if r.status_code != 200:
            issues.append(f"/api/lab/visa {r.status_code}")
        else:
            v = r.json()
            print(f"  answer len: {len(v['answer'])}")
            print(f"  sources: {len(v['sources'])}")
            print(f"  evidence_regions: {len(v['evidence_regions'])}")
            print(f"  timing: {v['timing_ms']}")
            print(f"  note: {v['note']}")
            for r in v['evidence_regions'][:5]:
                print(f"    cite=[{r['citation']}] page={r['page_number']} type={r['label']:10s} score={r['score']:.3f} bbox=({r['bbox']['x0']:.0f},{r['bbox']['y0']:.0f}~{r['bbox']['x1']:.0f},{r['bbox']['y1']:.0f})")
            if not v['answer']: issues.append("visa empty answer")
            # Should have at least one region per source
            if len(v['evidence_regions']) == 0 and v['sources']:
                issues.append("visa: no regions despite sources")

        # ---- GMM
        banner("[6] /api/lab/gmm")
        r = await c.post(f"{BASE}/api/lab/gmm", json={"query": Q, "top_k": 5, "candidates": 20})
        if r.status_code != 200:
            issues.append(f"/api/lab/gmm {r.status_code}")
        else:
            g = r.json()
            print(f"  fixed={g['fixed_top_k']} dynamic={g['dynamic_top_k']} cutoff={g['cutoff_score']:.3f}")
            print(f"  components: {g['components']}")
            print(f"  histogram bins: {len(g['histogram'])}, total count: {sum(b['count'] for b in g['histogram'])}")
            print(f"  note: {g['note']}")
            if not g['histogram']: issues.append("gmm: empty histogram")

        # ---- Region (likely empty)
        banner("[7] /api/lab/region/query")
        r = await c.post(f"{BASE}/api/lab/region/query", json={"query": Q, "top_k": 5})
        if r.status_code != 200:
            issues.append(f"/api/lab/region/query {r.status_code}")
        else:
            rg = r.json()
            print(f"  hits: {len(rg['hits'])}")
            print(f"  note: {rg['note']}")

        # ---- Index regions for one doc (smallest first) — async + poll
        smallest = min(completed, key=lambda d: d.get("total_pages") or 999)
        first = smallest
        banner(f"[8] /api/lab/region/index/{first['id']} (smallest={first['total_pages']}p, async + poll)")
        r = await c.post(f"{BASE}/api/lab/region/index/{first['id']}", timeout=10)
        print(f"  trigger status={r.status_code} body={r.json()}")
        if r.status_code != 200:
            issues.append(f"region index trigger failed: {r.status_code}")
        # Poll status
        last_progress = ""
        for i in range(180):       # 6 min max
            await asyncio.sleep(2)
            sr = await c.get(f"{BASE}/api/lab/region/status/{first['id']}", timeout=10)
            if sr.status_code != 200:
                issues.append(f"region status poll failed: {sr.status_code}")
                break
            st = sr.json()
            line = f"  state={st.get('state'):8s} page={st.get('current_page')}/{st.get('total_pages')} indexed={st.get('indexed')}"
            if line != last_progress:
                print(line)
                last_progress = line
            if st.get("state") in ("completed", "failed"):
                if st.get("errors", 0) > 0 and st.get("indexed", 0) == 0:
                    issues.append(f"region index all-errors: {st}")
                break
        else:
            issues.append("region index never completed in 6 min")

        # ---- Region query again after indexing — wait for indexing to finish
        banner("[9] /api/lab/region/query (post-index)")
        wait_idx = 0
        while wait_idx < 60:
            sr = await c.get(f"{BASE}/api/lab/region/status/{first['id']}", timeout=15)
            st = sr.json() if sr.status_code == 200 else {}
            if st.get("state") not in ("running", "pending"):
                break
            await asyncio.sleep(3)
            wait_idx += 1
        try:
            r = await c.post(f"{BASE}/api/lab/region/query", json={"query": Q, "top_k": 5}, timeout=60)
            if r.status_code == 200:
                rg = r.json()
                print(f"  hits: {len(rg['hits'])}")
                for h in rg['hits'][:3]:
                    print(f"    page={h['page_number']} idx={h['element_index']} type={h['element_type']:10s} score={h['score']:.3f}")
                if len(rg['hits']) == 0:
                    issues.append("region query: 0 hits after indexing")
            else:
                issues.append(f"region query post-index failed: {r.status_code} {r.text[:200]}")
        except Exception as e:
            issues.append(f"region query post-index timeout: {type(e).__name__}")

        # ---- Image fetch sanity
        banner("[10] Image fetch")
        r = await c.get(f"{BASE}/api/images/{first['id']}/page_1.png")
        print(f"  page_1.png status={r.status_code} len={len(r.content)}")
        if r.status_code != 200: issues.append(f"image fetch failed {r.status_code}")
        # placeholder
        r = await c.get(f"{BASE}/api/images/nonexistent/page_99.png")
        print(f"  placeholder status={r.status_code} len={len(r.content)}")

        # ---- Layout
        banner("[11] Document layout")
        r = await c.get(f"{BASE}/api/documents/{first['id']}/layout/1")
        print(f"  layout/1 status={r.status_code}")
        if r.status_code == 200:
            l = r.json()
            print(f"  page_size={l.get('page_width')}x{l.get('page_height')}, elements={len(l.get('elements', []))}")
            types = {}
            for e in l.get("elements", []):
                types[e["element_type"]] = types.get(e["element_type"], 0) + 1
            print(f"  element types: {types}")
            if not l.get("elements"):
                issues.append(f"doc {first['id']} page 1 has no layout elements")

    banner("ISSUES FOUND")
    if not issues:
        print("  NONE — all checks pass deeply!")
    else:
        for i in issues:
            print(f"  [!] {i}")
    return issues


if __name__ == "__main__":
    issues = asyncio.run(main())
    sys.exit(1 if issues else 0)
